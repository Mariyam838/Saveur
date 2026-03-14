from flask import Flask, render_template, request, jsonify, redirect, url_for
import urllib.request
import urllib.parse
import json
import re

app = Flask(__name__)
MEALDB = "https://www.themealdb.com/api/json/v1/1"

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}

def get_steps(raw):
    raw = (raw or "").strip()
    parts = re.split(r'\r?\n\r?\n|(?<=\.)\s+(?=[A-Z])', raw)
    steps = [p.strip() for p in parts if len(p.strip()) > 15][:14]
    return steps if steps else [raw]

# ── Fetch one representative meal image per category ──
def get_category_images():
    """Returns dict: category_name -> meal thumb URL"""
    result = {}
    cats_data = fetch(f"{MEALDB}/categories.php")
    for cat in (cats_data.get("categories") or []):
        name  = cat.get("strCategory", "")
        thumb = cat.get("strCategoryThumb", "")
        if name and thumb:
            result[name] = thumb
    return result

# ── Fetch one representative meal image per area ──
def get_area_images():
    """Returns dict: area_name -> meal thumb URL"""
    result = {}
    areas_data = fetch(f"{MEALDB}/list.php?a=list")
    for area in (areas_data.get("meals") or []):
        name = area.get("strArea", "")
        if not name:
            continue
        meals = fetch(f"{MEALDB}/filter.php?a={urllib.parse.quote(name)}")
        meal_list = meals.get("meals") or []
        if meal_list:
            result[name] = meal_list[0].get("strMealThumb", "")
    return result

# Cache at startup (populated lazily on first request)
_CATEGORY_IMAGES = {}
_AREA_IMAGES = {}

def ensure_images():
    global _CATEGORY_IMAGES, _AREA_IMAGES
    if not _CATEGORY_IMAGES:
        _CATEGORY_IMAGES = get_category_images()
    if not _AREA_IMAGES:
        _AREA_IMAGES = get_area_images()

# ── Ingredient images from TheMealDB (these work reliably) ──
INGREDIENT_SLUGS = {
    "Chicken":  "Chicken",
    "Salmon":   "Salmon",
    "Tomato":   "Tomatoes",
    "Garlic":   "Garlic",
    "Egg":      "Eggs",
    "Cheese":   "Cheddar%20Cheese",
    "Butter":   "Butter",
    "Rice":     "Rice",
    "Pasta":    "Pasta",
    "Lemon":    "Lemon",
    "Broccoli": "Broccoli",
    "Carrot":   "Carrots",
    "Ginger":   "Ginger",
    "Mushroom": "Mushrooms",
}

AREA_CODES = {
    "Italian":"IT","Chinese":"CN","French":"FR","Thai":"TH","Indian":"IN",
    "Japanese":"JP","Mexican":"MX","American":"US","British":"GB","Greek":"GR",
    "Moroccan":"MA","Spanish":"ES","Canadian":"CA","Croatian":"HR","Dutch":"NL",
    "Egyptian":"EG","Filipino":"PH","Irish":"IE","Jamaican":"JM","Kenyan":"KE",
    "Malaysian":"MY","Polish":"PL","Portuguese":"PT","Russian":"RU","Tunisian":"TN",
    "Turkish":"TR","Vietnamese":"VN",
}

CATEGORY_ICONS = {
    "Beef":"🥩","Chicken":"🍗","Seafood":"🦞","Dessert":"🍰","Pasta":"🍝",
    "Vegetarian":"🥦","Lamb":"🐑","Breakfast":"🍳","Side":"🫕","Starter":"🥗",
    "Vegan":"🌿","Pork":"🥓","Goat":"🐐","Miscellaneous":"✨",
}

PRIORITY_CUISINES = ["Italian","Chinese","French","Thai","Indian","Japanese","Mexican","American","British","Greek","Moroccan","Spanish"]
PRIORITY_CATS     = ["Beef","Chicken","Seafood","Dessert","Pasta","Vegetarian","Lamb","Breakfast","Side","Starter","Vegan"]


@app.route("/")
def index():
    ensure_images()
    # Build cuisine list with live images
    cuisines = []
    for name in PRIORITY_CUISINES:
        img = _AREA_IMAGES.get(name, "")
        cuisines.append({"name": name, "code": AREA_CODES.get(name, ""), "img": img})

    # Build category list with live category thumbnails
    categories = []
    for name in PRIORITY_CATS:
        img = _CATEGORY_IMAGES.get(name, "")
        categories.append({"name": name, "icon": CATEGORY_ICONS.get(name, "🍽️"), "img": img})

    # Build ingredient list (TheMealDB ingredient images are always reliable)
    ingredients = []
    for name, slug in INGREDIENT_SLUGS.items():
        img = f"https://www.themealdb.com/images/ingredients/{slug}-Small.png"
        ingredients.append({"name": name, "img": img})

    # Featured meals
    featured_data = fetch(f"{MEALDB}/search.php?s=chicken")
    meals = (featured_data.get("meals") or [])[:9]

    return render_template("index.html",
        cuisines=cuisines, categories=categories, ingredients=ingredients,
        meals=meals, query="", search_type="name")


@app.route("/search")
def search():
    ensure_images()
    q           = request.args.get("q", "").strip()
    search_type = request.args.get("type", "name")
    meals       = []

    if not q:
        return redirect(url_for("index"))

    if search_type == "name":
        data  = fetch(f"{MEALDB}/search.php?s={urllib.parse.quote(q)}")
        meals = data.get("meals") or []
    elif search_type == "ingredient":
        data  = fetch(f"{MEALDB}/filter.php?i={urllib.parse.quote(q)}")
        meals = (data.get("meals") or [])[:12]
    elif search_type == "category":
        data  = fetch(f"{MEALDB}/filter.php?c={urllib.parse.quote(q)}")
        meals = (data.get("meals") or [])[:12]
    elif search_type == "area":
        data  = fetch(f"{MEALDB}/filter.php?a={urllib.parse.quote(q)}")
        meals = (data.get("meals") or [])[:12]

    error = f'No recipes found for "{q}"' if not meals else None

    # Rebuild circle data for the results page
    cuisines = [{"name": n, "code": AREA_CODES.get(n,""), "img": _AREA_IMAGES.get(n,"")}
                for n in PRIORITY_CUISINES]
    categories = [{"name": n, "icon": CATEGORY_ICONS.get(n,"🍽️"), "img": _CATEGORY_IMAGES.get(n,"")}
                  for n in PRIORITY_CATS]
    ingredients = [{"name": n, "img": f"https://www.themealdb.com/images/ingredients/{s}-Small.png"}
                   for n, s in INGREDIENT_SLUGS.items()]

    return render_template("index.html",
        cuisines=cuisines, categories=categories, ingredients=ingredients,
        meals=meals, query=q, search_type=search_type, error=error)


@app.route("/recipe/<meal_id>")
def recipe(meal_id):
    data  = fetch(f"{MEALDB}/lookup.php?i={meal_id}")
    meals = data.get("meals")
    if not meals:
        return redirect(url_for("index"))
    m = meals[0]
    ingredients = []
    for i in range(1, 21):
        name    = (m.get(f"strIngredient{i}") or "").strip()
        measure = (m.get(f"strMeasure{i}")    or "").strip()
        if name:
            ingredients.append({"name": name, "measure": measure})
    steps = get_steps(m.get("strInstructions", ""))
    return render_template("recipe.html", m=m, ingredients=ingredients, steps=steps)


if __name__ == "__main__":
    app.run(debug=True)