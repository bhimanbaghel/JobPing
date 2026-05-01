from .greenhouse import GreenhouseScraper


class AirbnbScraper(GreenhouseScraper):
    company_slug = "airbnb"
    board_token = "airbnb"
