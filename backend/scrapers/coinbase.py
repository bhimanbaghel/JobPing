from .greenhouse import GreenhouseScraper


class CoinbaseScraper(GreenhouseScraper):
    company_slug = "coinbase"
    board_token = "coinbase"
