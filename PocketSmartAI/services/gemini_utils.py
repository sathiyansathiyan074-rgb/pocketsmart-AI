import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from services.catalog import platform_links

load_dotenv(
    Path(__file__).resolve().parent.parent / ".env"
)


def _get_client():

    api_key = os.getenv(
        "GEMINI_API_KEY",
        ""
    ).strip()

    if not api_key:
        return None

    try:

        from google import genai

        return genai.Client(
            api_key=api_key
        )

    except Exception:

        return None


def _extract_json(text: str):

    if not text:
        return None

    text = text.strip()

    if text.startswith("```"):

        text = (
            text
            .replace("```json", "", 1)
            .replace("```", "")
            .strip()
        )

    try:

        return json.loads(text)

    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:

        try:

            return json.loads(
                text[start:end + 1]
            )

        except Exception:
            return None

    return None


def _ask_gemini(
    prompt: str,
    image_path: Optional[str] = None
):

    client = _get_client()

    if client is None:
        return None

    model = os.getenv(
        "GEMINI_MODEL",
        "gemini-2.5-flash"
    )

    try:

        contents = [prompt]

        if image_path:

            from PIL import Image

            image = Image.open(image_path)

            contents.append(image)

        response = client.models.generate_content(
            model=model,
            contents=contents
        )

        return _extract_json(
            response.text or ""
        )

    except Exception as error:

        print(
            "Gemini error:",
            error
        )

        return None


# --------------------------------------------------
# HOME FALLBACK
# --------------------------------------------------

def _home_fallback(data):

    budget = float(
        data["budget"]
    )

    requested = [
        (
            "Lighting",
            int(data.get("lights", 0))
        ),
        (
            "Ceiling Fans",
            int(data.get("fans", 0))
        ),
        (
            "Furniture",
            int(data.get("furniture", 0))
        ),
        (
            "Dining Table",
            int(data.get("dining_tables", 0))
        )
    ]

    active = [
        item
        for item in requested
        if item[1] > 0
    ]

    if not active:

        active = [
            ("Lighting", 2),
            ("Furniture", 1)
        ]

    allocation = budget / len(active)

    categories = []

    total_used = 0

    for category, quantity in active:

        unit_price = round(
            allocation / max(quantity, 1),
            2
        )

        category_total = round(
            unit_price * quantity,
            2
        )

        total_used += category_total

        categories.append(
            {
                "category": category,
                "allocation": category_total,

                "items": [
                    {
                        "name": (
                            f"Budget {category}"
                        ),

                        "description": (
                            f"Practical "
                            f"{category.lower()} "
                            f"option for "
                            f"{data['room_type']}"
                        ),

                        "price": unit_price,
                        "quantity": quantity,

                        "links": platform_links(
                            f"{category} "
                            f"{data['room_type']}"
                        )
                    }
                ]
            }
        )

    return {
        "total_budget": budget,

        "remaining_budget": round(
            max(
                budget - total_used,
                0
            ),
            2
        ),

        "categories": categories,

        "additional_suggestions": [
            "Prioritize essential items first.",
            "Compare prices across platforms before purchasing.",
            "Keep a small buffer for delivery and installation."
        ]
    }


# --------------------------------------------------
# PARTY FALLBACK
# --------------------------------------------------

def _party_fallback(data):

    budget = float(
        data["budget"]
    )

    categories = []

    portions = [
        ("Venue", 0.30),
        ("Catering", 0.40),
        ("Decoration", 0.15),
        ("Entertainment", 0.15)
    ]

    for name, percentage in portions:

        if (
            name == "Catering"
            and not data.get("catering")
        ):
            continue

        if (
            name == "Decoration"
            and not data.get("decoration")
        ):
            continue

        if (
            name == "Entertainment"
            and not data.get("entertainment")
        ):
            continue

        allocation = round(
            budget * percentage,
            2
        )

        if name == "Catering":
            link_category = "food"

        elif name == "Venue":
            link_category = "stay"

        else:
            link_category = "shopping"

        categories.append(
            {
                "category": name,
                "allocation": allocation,

                "items": [
                    {
                        "name": (
                            f"{name} option"
                        ),

                        "description": (
                            f"Suitable for "
                            f"{data['guests']} guests"
                        ),

                        "price": allocation,
                        "quantity": 1,

                        "links": platform_links(
                            f"{data['event_type']} {name}",
                            link_category
                        )
                    }
                ]
            }
        )

    allocated = sum(
        category["allocation"]
        for category in categories
    )

    return {
        "total_budget": budget,

        "remaining_budget": round(
            max(
                budget - allocated,
                0
            ),
            2
        ),

        "categories": categories,

        "additional_suggestions": [
            "Confirm vendor availability before payment.",
            "Keep a contingency amount for last-minute changes."
        ]
    }


# --------------------------------------------------
# JEWELRY FALLBACK
# --------------------------------------------------

def _jewelry_fallback(data):

    budget = float(
        data["budget"]
    )

    jewelry_types = [
        "Bracelet",
        "Earrings",
        "Necklace",
        "Watch"
    ]

    each_price = round(
        budget / len(jewelry_types),
        2
    )

    items = []

    for jewelry in jewelry_types:

        items.append(
            {
                "name": jewelry,

                "description": (
                    f"{data['preferences']} "
                    f"style for "
                    f"{data['occasion']}"
                ),

                "price": each_price,
                "quantity": 1,

                "links": platform_links(
                    f"{jewelry} "
                    f"{data['occasion']} "
                    f"{data['preferences']}"
                )
            }
        )

    return {
        "total_budget": budget,
        "remaining_budget": 0,

        "outfit_analysis": {
            "colors": [],
            "style": data["preferences"],
            "metal": "Not determined",
            "note": (
                "Upload an outfit image "
                "for image-aware recommendations."
            )
        },

        "categories": [
            {
                "category":
                    "Jewelry Recommendations",

                "allocation": budget,

                "items": items
            }
        ],

        "additional_suggestions": [
            "Match metal tone with outfit accessories.",
            "Choose one statement piece and keep other pieces balanced."
        ]
    }


# --------------------------------------------------
# HOME AI
# --------------------------------------------------

def generate_home_recommendations(data):

    prompt = f"""
You are PocketSmart AI.

Create a personalized home interior
budget plan.

Return ONLY valid JSON.

Requirements:

- Stay within the user's budget.
- Balance functionality, style and price.
- Recommend practical products.
- Consider the requested quantities.
- Suggested platforms:
  Amazon, Flipkart and IKEA.

User input:

{json.dumps(data)}

Return exactly this structure:

{{
    "total_budget": number,
    "remaining_budget": number,
    "categories": [
        {{
            "category": string,
            "allocation": number,
            "items": [
                {{
                    "name": string,
                    "description": string,
                    "price": number,
                    "quantity": number
                }}
            ]
        }}
    ],
    "additional_suggestions": [
        string
    ]
}}
"""

    result = _ask_gemini(prompt)

    if result:

        for category in result.get(
            "categories",
            []
        ):

            for item in category.get(
                "items",
                []
            ):

                item["links"] = platform_links(
                    item.get(
                        "name",
                        "home product"
                    )
                )

        return result

    return _home_fallback(data)


# --------------------------------------------------
# PARTY AI
# --------------------------------------------------

def generate_party_recommendations(data):

    prompt = f"""
You are PocketSmart AI.

Create a party budget plan.

Return ONLY valid JSON.

Consider:

- Total budget
- Guest count
- Event type
- Venue type
- Catering
- Decoration
- Entertainment
- Additional requirements

Allocate the budget sensibly.

Use:
- Swiggy
- Zomato
- OYO
- Amazon
- Flipkart

when relevant.

Input:

{json.dumps(data)}

Return:

{{
    "total_budget": number,
    "remaining_budget": number,
    "categories": [
        {{
            "category": string,
            "allocation": number,
            "items": [
                {{
                    "name": string,
                    "description": string,
                    "price": number,
                    "quantity": number
                }}
            ]
        }}
    ],
    "additional_suggestions": [
        string
    ]
}}
"""

    result = _ask_gemini(prompt)

    if result:

        for category in result.get(
            "categories",
            []
        ):

            category_name = (
                category.get(
                    "category",
                    ""
                ).lower()
            )

            if "catering" in category_name:
                link_category = "food"

            elif "venue" in category_name:
                link_category = "stay"

            else:
                link_category = "shopping"

            for item in category.get(
                "items",
                []
            ):

                item["links"] = platform_links(
                    item.get(
                        "name",
                        "party service"
                    ),
                    link_category
                )

        return result

    return _party_fallback(data)


# --------------------------------------------------
# JEWELRY AI
# --------------------------------------------------

def generate_jewelry_recommendations(
    data,
    image_path=None
):

    prompt = f"""
You are PocketSmart AI.

Recommend jewelry within the exact budget.

Consider:

- Budget
- Occasion
- Style preference
- Outfit image if supplied

If an image is provided:

1. Analyze outfit colors.
2. Analyze overall style.
3. Recommend suitable jewelry.
4. Explain why the jewelry matches.

Suggested platforms:

Amazon
Flipkart

Return ONLY valid JSON.

Input:

{json.dumps(data)}

Return:

{{
    "total_budget": number,
    "remaining_budget": number,

    "outfit_analysis": {{
        "colors": [string],
        "style": string,
        "metal": string,
        "note": string
    }},

    "categories": [
        {{
            "category": string,
            "allocation": number,

            "items": [
                {{
                    "name": string,
                    "description": string,
                    "price": number,
                    "quantity": number
                }}
            ]
        }}
    ],

    "additional_suggestions": [
        string
    ]
}}
"""

    result = _ask_gemini(
        prompt,
        image_path
    )

    if result:

        for category in result.get(
            "categories",
            []
        ):

            for item in category.get(
                "items",
                []
            ):

                item["links"] = platform_links(
                    item.get(
                        "name",
                        "jewelry"
                    )
                )

        return result

    return _jewelry_fallback(data)