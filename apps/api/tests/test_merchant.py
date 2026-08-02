from app.services.merchant import normalize_merchant


class TestNormalizeMerchant:
    def test_strips_square_prefix(self):
        assert normalize_merchant("SQ *COFFEE BAR KEARNY San Francisco CA").startswith(
            "COFFEE BAR"
        )

    def test_strips_toast_prefix(self):
        assert normalize_merchant("TST* CHAAT DINER SF CA").startswith("CHAAT DINER")

    def test_strips_doordash_prefix_and_phone(self):
        # DD * prefix, trailing phone number, and state all removed.
        assert normalize_merchant("DD *DOORDASH APPLEBEES 855-431-0459 CA") == (
            "DOORDASH APPLEBEES"
        )

    def test_strips_trailing_state_and_store_number(self):
        assert normalize_merchant("STARBUCKS STORE #1122 WA") == "STARBUCKS STORE"

    def test_plain_merchant_unchanged(self):
        assert normalize_merchant("WHOLE FOODS MARKET") == "WHOLE FOODS MARKET"

    def test_empty(self):
        assert normalize_merchant("") == ""
        assert normalize_merchant(None) == ""  # type: ignore[arg-type]

    def test_prefix_only_keeps_original(self):
        # Stripping must never empty out the merchant entirely.
        assert normalize_merchant("SQ *") == "SQ *"
