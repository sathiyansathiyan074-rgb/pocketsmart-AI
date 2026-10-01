from urllib.parse import quote_plus


def platform_links(
    query: str,
    category: str = "shopping"
):

    encoded_query = quote_plus(query)

    if category == "food":

        return [
            {
                "platform": "Swiggy",
                "url": (
                    "https://www.swiggy.com/search"
                    f"?query={encoded_query}"
                )
            },
            {
                "platform": "Zomato",
                "url": (
                    "https://www.zomato.com/search"
                    f"?query={encoded_query}"
                )
            }
        ]

    if category == "stay":

        return [
            {
                "platform": "OYO",
                "url": (
                    "https://www.oyorooms.com/search"
                    f"?location={encoded_query}"
                )
            }
        ]

    return [
        {
            "platform": "Amazon",
            "url": (
                "https://www.amazon.in/s"
                f"?k={encoded_query}"
            )
        },
        {
            "platform": "Flipkart",
            "url": (
                "https://www.flipkart.com/search"
                f"?q={encoded_query}"
            )
        },
        {
            "platform": "IKEA",
            "url": (
                "https://www.ikea.com/in/en/search/"
                f"?q={encoded_query}"
            )
        }
    ]