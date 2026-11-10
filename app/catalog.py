"""商品目录：列表页、详情页和 seed 共用同一份数据。

本项目不额外建 products 表，评论仍用 target_name 关联商品；
这样保持三张表，同时保证商品名、评论内容、关键词来自同一份目录。
"""
from __future__ import annotations

PRODUCTS = [
    {
        "slug": "noise-cancelling-headphones",
        "name": "降噪耳机",
        "category": "数码",
        "price": 399,
        "original_price": 599,
        "emoji": "🎧",
        "image": "images/products/headphones.svg",
        "photo": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=1200&q=80",
        "photo_local": "images/products/headphones.jpg",
        "color": "#dbeafe",
        "tagline": "通勤降噪，轻量佩戴",
        "description": "40mm 动圈单元，主动降噪，适合地铁、办公室和长时间佩戴。",
        "features": ["主动降噪", "30 小时续航", "蓝牙 5.3"],
        "keywords": ["降噪", "音质", "佩戴", "续航", "蓝牙"],
        "positive": [
            "降噪效果很好，地铁里也安静，戴一天不夹耳朵。",
            "音质清晰，低频有力，续航也够用。",
            "连接稳定，蓝牙配对很快，通勤戴着很舒服。",
        ],
        "negative": [
            "戴了一天耳朵就发炎，这耳机真是绝了。",
            "降噪一般，地铁里还是能听到广播声。",
            "用了三天就断连，客服也不回消息。",
        ],
        "neutral": [
            "包装一般，功能符合预期。",
            "音质中规中矩，降噪没有宣传的那么强。",
        ],
    },
    {
        "slug": "mechanical-keyboard",
        "name": "机械键盘",
        "category": "数码",
        "price": 299,
        "original_price": 399,
        "emoji": "⌨️",
        "image": "images/products/keyboard.svg",
        "photo": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=1200&q=80",
        "photo_local": "images/products/keyboard.jpg",
        "color": "#ede9fe",
        "tagline": "客制化手感，灯效拉满",
        "description": "87 键热插拔，PBT 键帽，适合办公、代码和游戏场景。",
        "features": ["热插拔", "PBT 键帽", "RGB 灯效"],
        "keywords": ["手感", "轴体", "键帽", "灯效", "打字"],
        "positive": [
            "键盘手感很好，敲代码很舒服，灯效也漂亮。",
            "轴体顺滑，键帽做工扎实，打字声音很好听。",
            "连接稳定，游戏里没有延迟，灯效可以自定义。",
        ],
        "negative": [
            "用了一周键帽就松动，品控一般。",
            "轴体有弹簧音，打字手感不如预期。",
        ],
        "neutral": [
            "外观和图片差不多，手感中规中矩。",
            "灯效不错，其他方面还没深入体验。",
        ],
    },
    {
        "slug": "vacuum-bottle",
        "name": "保温杯",
        "category": "家居",
        "price": 129,
        "original_price": 169,
        "emoji": "🥤",
        "image": "images/products/bottle.svg",
        "photo": "https://images.unsplash.com/photo-1602143407151-7111542de6e8?auto=format&fit=crop&w=1200&q=80",
        "photo_local": "images/products/bottle.jpg",
        "color": "#dcfce7",
        "tagline": "316 不锈钢，长效保温",
        "description": "500ml 容量，杯盖防漏，适合通勤、办公室和短途出行。",
        "features": ["316 不锈钢", "12 小时保温", "防漏杯盖"],
        "keywords": ["保温", "杯盖", "容量", "漏水", "清洗"],
        "positive": [
            "保温效果超出预期，早上装的热水下午还烫。",
            "杯盖不漏水，容量刚好，放包里也方便。",
            "内胆好清洗，没有异味，保温也够用。",
        ],
        "negative": [
            "杯盖漏水，放包里把电脑打湿了。",
            "保温效果一般，两个小时就凉了。",
        ],
        "neutral": [
            "容量合适，做工中规中矩。",
            "保温还行，杯盖有点紧。",
        ],
    },
    {
        "slug": "running-shoes",
        "name": "运动鞋",
        "category": "运动",
        "price": 269,
        "original_price": 359,
        "emoji": "👟",
        "image": "images/products/shoes.svg",
        "photo": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=1200&q=80",
        "photo_local": "images/products/shoes.jpg",
        "color": "#ffedd5",
        "tagline": "轻量缓震，日常慢跑",
        "description": "透气网面，橡胶大底，适合 3—5 公里日常慢跑和通勤。",
        "features": ["轻量", "缓震", "透气"],
        "keywords": ["轻便", "跑步", "尺码", "磨脚", "透气"],
        "positive": [
            "鞋子很轻，跑步不磨脚，尺码也标准。",
            "透气性不错，跑完脚不闷，缓震也够用。",
            "鞋底软，日常走路很舒服，尺码建议按正常选。",
        ],
        "negative": [
            "鞋子磨脚，走两步就起泡，不推荐。",
            "尺码偏小，透气一般，跑步有点闷。",
        ],
        "neutral": [
            "外观和图片差不多，脚感一般。",
            "轻便倒是轻便，缓震一般。",
        ],
    },
    {
        "slug": "coffee-beans",
        "name": "咖啡豆",
        "category": "食品",
        "price": 89,
        "original_price": 109,
        "emoji": "☕",
        "image": "images/products/coffee.svg",
        "photo": "https://images.unsplash.com/photo-1447933601403-0c6688de566e?auto=format&fit=crop&w=1200&q=80",
        "photo_local": "images/products/coffee.jpg",
        "color": "#fef3c7",
        "tagline": "中深烘焙，坚果巧克力调",
        "description": "500g 阿拉比卡咖啡豆，适合手冲和意式，开袋后建议冷藏保存。",
        "features": ["中深烘焙", "阿拉比卡", "500g"],
        "keywords": ["香气", "油脂", "酸度", "烘焙", "回购"],
        "positive": [
            "咖啡豆很香，油脂丰富，会回购。",
            "烘焙度刚好，酸度柔和，手冲很好喝。",
            "做意式油脂很厚，香气也足。",
        ],
        "negative": [
            "咖啡豆有股陈味，喝起来发酸。",
            "烘焙太深，苦味重，香气不足。",
        ],
        "neutral": [
            "口感中规中矩，酸度比预期高一点。",
            "香气一般，油脂还可以。",
        ],
    },
    {
        "slug": "power-bank",
        "name": "充电宝",
        "category": "数码",
        "price": 159,
        "original_price": 199,
        "emoji": "🔋",
        "image": "images/products/powerbank.svg",
        "photo": "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?auto=format&fit=crop&w=1200&q=80",
        "photo_local": "images/products/powerbank.jpg",
        "color": "#e0f2fe",
        "tagline": "10000mAh，双向快充",
        "description": "自带线，支持 22.5W 快充，体积小巧，可带上飞机。",
        "features": ["10000mAh", "22.5W 快充", "自带线"],
        "keywords": ["充电速度", "发热", "容量", "便携", "体积"],
        "positive": [
            "充电速度很快，体积小，出门带着方便。",
            "容量够用，给手机充两次还有电，发热控制不错。",
            "自带线很方便，快充速度也稳定。",
        ],
        "negative": [
            "充电宝发热严重，充到一半就停了。",
            "容量虚标，充电速度也慢。",
        ],
        "neutral": [
            "容量和标称差不多，充电速度一般。",
            "体积不大，发热有点明显。",
        ],
    },
    {
        "slug": "monitor",
        "name": "显示器",
        "category": "数码",
        "price": 899,
        "original_price": 1099,
        "emoji": "🖥️",
        "image": "images/products/monitor.svg",
        "photo": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=1200&q=80",
        "photo_local": "images/products/monitor.jpg",
        "color": "#e2e8f0",
        "tagline": "2K 护眼，办公设计",
        "description": "27 英寸 2K IPS 面板，低蓝光，75Hz 刷新率，适合办公和轻度设计。",
        "features": ["27 英寸 2K", "IPS", "低蓝光"],
        "keywords": ["色彩", "坏点", "刷新率", "支架", "屏幕"],
        "positive": [
            "屏幕色彩很正，看文档不累眼。",
            "2K 清晰，支架调节方便，办公很舒服。",
            "刷新率够用，色彩没有明显偏色。",
        ],
        "negative": [
            "显示器有坏点，换货流程很麻烦。",
            "支架太占地方，色彩偏冷。",
        ],
        "neutral": [
            "显示效果中规中矩，支架有点占地方。",
            "色彩还行，刷新率一般。",
        ],
    },
    {
        "slug": "shampoo",
        "name": "洗发水",
        "category": "个护",
        "price": 69,
        "original_price": 89,
        "emoji": "🧴",
        "image": "images/products/shampoo.svg",
        "photo": "https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?auto=format&fit=crop&w=1200&q=80",
        "photo_local": "images/products/shampoo.jpg",
        "color": "#fce7f3",
        "tagline": "控油蓬松，温和清洁",
        "description": "500ml 氨基酸配方，适合油性头皮，香味清爽不冲。",
        "features": ["氨基酸", "控油", "500ml"],
        "keywords": ["香味", "顺滑", "头皮", "控油", "泡沫"],
        "positive": [
            "洗完头发很顺，香味也不冲。",
            "控油效果不错，头皮清爽，泡沫丰富。",
            "香味高级，洗完不干，顺滑度可以。",
        ],
        "negative": [
            "洗完头皮发痒，可能不适合我。",
            "控油一般，第二天就油了，香味太浓。",
        ],
        "neutral": [
            "泡沫一般，香味比较淡。",
            "顺滑度还行，控油没太大感觉。",
        ],
    },
]

PRODUCT_NAMES = {product["name"] for product in PRODUCTS}
CATEGORIES = sorted({product["category"] for product in PRODUCTS})


def get_product(slug: str) -> dict | None:
    return next((product for product in PRODUCTS if product["slug"] == slug), None)


def get_product_by_name(name: str) -> dict | None:
    return next((product for product in PRODUCTS if product["name"] == name), None)


def slug_for_name(name: str) -> str | None:
    product = get_product_by_name(name)
    return product["slug"] if product else None
