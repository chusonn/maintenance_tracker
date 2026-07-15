from datetime import date

from app.services.excel_io import clean_due_date, clean_rent_value, parse_uk_date


class TestCleanRentValue:
    def test_plain_number(self):
        assert clean_rent_value("1250") == 1250.0

    def test_strips_pound_sign_and_commas(self):
        assert clean_rent_value("£1,250.00") == 1250.0

    def test_multiline_takes_first_valid(self):
        assert clean_rent_value("£1,100\n£1,200") == 1100.0

    def test_garbage_returns_none(self):
        assert clean_rent_value("TBC") is None

    def test_missing_returns_none(self):
        assert clean_rent_value(None) is None
        assert clean_rent_value("") is None
        assert clean_rent_value(float("nan")) is None


class TestParseUkDate:
    def test_ddmmyyyy_is_day_first(self):
        assert parse_uk_date("05/03/2024") == date(2024, 3, 5)

    def test_multiline_returns_first_date(self):
        assert parse_uk_date("01/02/2023\n15/08/2024") == date(2023, 2, 1)

    def test_datetime_passthrough(self):
        from datetime import datetime

        assert parse_uk_date(datetime(2024, 6, 1, 12, 30)) == date(2024, 6, 1)

    def test_invalid_returns_none(self):
        assert parse_uk_date("not a date") is None
        assert parse_uk_date(None) is None


class TestCleanDueDate:
    def test_extracts_day(self):
        assert clean_due_date("15th") == 15
        assert clean_due_date(1) == 1

    def test_out_of_range_returns_none(self):
        assert clean_due_date("42") is None

    def test_missing_returns_none(self):
        assert clean_due_date(None) is None
        assert clean_due_date("") is None
