"""Flask 应用工厂。"""
from __future__ import annotations

import json
import logging
from datetime import timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

import click
from flask import Flask, g, jsonify, render_template, request, session, url_for
from sqlalchemy import text

from config import Config
from .extensions import CSRFError, csrf, db
from .models import User


def _wants_json() -> bool:
    return request.path.startswith("/api/")


def _json_error(code: str, message: str, status: int):
    return jsonify(ok=False, error={"code": code, "message": message}), status


def create_app(config_object=Config, **overrides) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    if overrides:
        app.config.update(overrides)

    # 会话生命周期：配置里是秒数，Flask 需要 timedelta
    lifetime = app.config.get("PERMANENT_SESSION_LIFETIME", 8 * 60 * 60)
    if isinstance(lifetime, (int, float)):
        app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(seconds=lifetime)

    review = float(app.config["REVIEW_THRESHOLD"])
    reject = float(app.config["REJECT_THRESHOLD"])
    if not (0 < review < reject < 1):
        raise RuntimeError(
            "阈值不合法：必须满足 0 < REVIEW_THRESHOLD < REJECT_THRESHOLD < 1"
        )

    if app.config["SECRET_KEY"] == "dev-only-change-me":
        app.logger.warning("正在使用开发默认 SECRET_KEY，答辩/部署前请修改 .env")

    Path(app.config["LOG_FILE"]).parent.mkdir(parents=True, exist_ok=True)
    _setup_logging(app)

    db.init_app(app)
    csrf.init_app(app)
    app.json.ensure_ascii = False

    # 延迟导入，确保 db 已初始化
    from .admin.routes import admin_bp
    from .auth.routes import auth_bp
    from .comment.routes import comment_bp
    from .product.routes import product_bp
    from .review.routes import review_bp
    from .stats.routes import stats_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(comment_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(stats_bp)

    @app.before_request
    def load_user():
        g.user = None
        user_id = session.get("user_id")
        if not user_id:
            return None
        user = db.session.get(User, user_id)
        if user is None or not user.is_active:
            session.clear()
            return None
        g.user = user
        return None

    @app.context_processor
    def inject_helpers():
        def page_url(page: int) -> str:
            endpoint = request.endpoint
            if not endpoint:
                return "#"
            args = request.args.to_dict(flat=True)
            args["page"] = page
            view_args = request.view_args or {}
            return url_for(endpoint, **view_args, **args)

        return {
            "current_user": g.get("user"),
            "page_url": page_url,
            "app_name": "AI 评论管理系统",
        }

    @app.template_filter("dt")
    def format_datetime(value, fmt: str = "%Y-%m-%d %H:%M"):
        if not value:
            return "-"
        return value.strftime(fmt)

    @app.template_filter("pct")
    def format_percent(value):
        try:
            return f"{float(value or 0) * 100:.1f}%"
        except (TypeError, ValueError):
            return "0.0%"

    @app.get("/healthz")
    def healthz():
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            return jsonify(status="error", db=False), 503
        return jsonify(
            status="ok",
            db=True,
            ai_enabled=bool(app.config["AI_ENABLED"]),
        )

    @app.errorhandler(403)
    def forbidden(error):
        if _wants_json():
            return _json_error("FORBIDDEN", "没有权限执行该操作", 403)
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        if _wants_json():
            return _json_error("NOT_FOUND", "资源不存在", 404)
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.exception("未处理的服务器异常")
        if _wants_json():
            return _json_error("INTERNAL_ERROR", "服务器内部错误", 500)
        return render_template("errors/500.html"), 500

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        if _wants_json():
            return _json_error("CSRF_INVALID", "CSRF 校验失败", 400)
        return render_template("errors/400.html", message="表单已过期，请刷新后重试"), 400

    @app.cli.command("init-db")
    def init_db_command():
        """创建三张表。"""
        db.create_all()
        print("数据库表已创建。")

    @app.cli.command("sentiment")
    @click.argument("text")
    def sentiment_command(text):
        """查看一条文本的规则情感分析结果。"""
        from .ai.sentiment import analyze_sentiment

        result = analyze_sentiment(text)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    # 启动预热：词库 + jieba；失败不影响启动
    with app.app_context():
        try:
            from .ai.keywords import initialize as init_keywords

            init_keywords()
        except Exception as exc:  # pragma: no cover - 环境相关
            app.logger.warning("关键词组件预热失败：%s", exc)
        try:
            from .ai.rules import get_matcher

            get_matcher()
        except Exception as exc:  # pragma: no cover - 环境相关
            app.logger.warning("敏感词库预热失败：%s", exc)

    return app


def _setup_logging(app: Flask) -> None:
    level = getattr(logging, str(app.config.get("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    app.logger.setLevel(level)
    log_file = Path(app.config["LOG_FILE"])
    if any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
        return
    handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    app.logger.addHandler(handler)
