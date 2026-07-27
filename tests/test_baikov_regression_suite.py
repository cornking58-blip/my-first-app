import unittest
from pathlib import Path

from backend.product_catalog import detect_group, extract_manufacturer, is_catalog_request
from backend.strict_catalog_ai import (
    build_strict_direct_answer,
    extract_single_product_candidate,
    is_short_contextual_fragment,
    select_catalog_substance_matches,
    select_unambiguous_catalog_match,
)


ROOT = Path(__file__).resolve().parents[1]
STRICT_SOURCE = (ROOT / "backend" / "strict_catalog_ai.py").read_text(encoding="utf-8")
SERVER_SOURCE = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")


class BaikovRegressionSuite(unittest.TestCase):
    def test_catalog_command_phrases(self):
        phrases = (
            "выпиши протравители Щёлково Агрохим",
            "выпиши все протравители AgroExpert Group",
            "покажи фунгициды компании Август",
            "перечисли инсектициды производителя",
            "дай список гербицидов компании",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertTrue(is_catalog_request(phrase))

    def test_group_detection(self):
        cases = {
            "выпиши гербициды компании": "herbicide",
            "выпиши фунгициды компании": "fungicide",
            "выпиши инсектициды компании": "insecticide",
            "выпиши протравители компании": "seed_treatment",
            "покажи препараты: обработка семян": "seed_treatment",
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(detect_group(phrase), expected)

    def test_manufacturer_extraction(self):
        cases = {
            "выпиши протравители Щёлково Агрохим": "Щёлково Агрохим",
            "выпиши все протравители AgroExpert Group": "AgroExpert Group",
            "покажи фунгициды компании Август": "Август",
            "дай список инсектицидов производителя Сингента": "Сингента",
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(extract_manufacturer(phrase), expected)

    def test_product_prefixes_are_removed(self):
        cases = {
            "препарат Цепелин": "Цепелин",
            "расскажи про препарат Цепелин": "Цепелин",
            "дай информацию о препарате Ронилан": "Ронилан",
            "фунгицид Амистар Голд": "Амистар Голд",
            "протравитель Туарег": "Туарег",
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(extract_single_product_candidate(phrase), expected)

    def test_active_substance_followups_are_cleaned(self):
        cases = {
            "а фамоксадон тогда для чего?": "фамоксадон",
            "а цимоксанил зачем?": "цимоксанил",
            "а протиоконазол для чего?": "протиоконазол",
            "а азоксистробин зачем?": "азоксистробин",
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(extract_single_product_candidate(phrase), expected)

    def test_active_substance_is_found_only_in_compositions(self):
        products = [
            {
                "product_name": "Улис",
                "product_key": "ulis",
                "product_group": "fungicide",
                "active_substances_raw": "Фамоксадон 225 г/кг + цимоксанил 300 г/кг",
            },
            {
                "product_name": "Крестраж",
                "product_key": "krestrazh",
                "product_group": "fungicide",
                "active_substances_raw": "Протиоконазол 80 г/л + тебуконазол 160 г/л",
            },
        ]
        famoxadone = select_catalog_substance_matches(products, "фамоксадон")
        prothioconazole = select_catalog_substance_matches(products, "протиоконазол")
        unknown = select_catalog_substance_matches(products, "несуществующее")
        self.assertEqual([item["product_name"] for item in famoxadone], ["Улис"])
        self.assertEqual([item["product_name"] for item in prothioconazole], ["Крестраж"])
        self.assertEqual(unknown, [])

    def test_exact_product_name_has_priority(self):
        products = [
            {"product_name": "Амистар Голд", "product_key": "amistar-gold"},
            {"product_name": "Амистар Топ", "product_key": "amistar-top"},
        ]
        match = select_unambiguous_catalog_match(products, "Амистар Голд")
        self.assertIsNotNone(match)
        self.assertEqual(match["product_key"], "amistar-gold")

    def test_unique_one_letter_typo_is_allowed(self):
        products = [
            {"product_name": "Ронилан", "product_key": "ronilan"},
            {"product_name": "Протазокс", "product_key": "protazox"},
        ]
        match = select_unambiguous_catalog_match(products, "Ранилан")
        self.assertIsNotNone(match)
        self.assertEqual(match["product_name"], "Ронилан")

    def test_ambiguous_partial_name_is_not_guessed(self):
        products = [
            {"product_name": "Амистар Голд", "product_key": "amistar-gold"},
            {"product_name": "Амистар Топ", "product_key": "amistar-top"},
        ]
        self.assertIsNone(select_unambiguous_catalog_match(products, "Амистар"))

    def test_short_contextual_fragments(self):
        self.assertTrue(is_short_contextual_fragment("Голд"))
        self.assertTrue(is_short_contextual_fragment("Амистар Голд"))
        self.assertFalse(is_short_contextual_fragment("выпиши препараты Голд"))
        self.assertFalse(is_short_contextual_fragment("что посоветуешь против ржавчины"))

    def test_missing_product_answer_does_not_hallucinate(self):
        answer = build_strict_direct_answer({
            "intent": "product_not_found",
            "missing_products": ["Неизвестный препарат"],
            "suggestions": ["Амистар Голд", "Амистар Топ"],
        })
        self.assertIn("угадывать не буду", answer)
        self.assertIn("Амистар Голд", answer)
        self.assertIn("Амистар Топ", answer)

    def test_field_question_is_not_mistaken_for_product(self):
        phrases = (
            "Что посоветуешь против ржавчины на подсолнечнике?",
            "Подбери схему против ложной мучнистой росы",
            "Какая норма на пшенице?",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIsNone(extract_single_product_candidate(phrase))

    def test_contextual_followup_contract_is_present(self):
        self.assertIn('"intent": "contextual_product_followup"', STRICT_SOURCE)
        self.assertIn("Используй предыдущие сообщения диалога", STRICT_SOURCE)
        self.assertIn("Не объявляй фрагмент новым препаратом", STRICT_SOURCE)

    def test_verified_substance_disables_web_fallback(self):
        self.assertIn('"intent": "active_substance"', STRICT_SOURCE)
        self.assertIn('"allow_web_fallback": False', STRICT_SOURCE)

    def test_model_receives_recent_chat_history(self):
        self.assertIn("for item in list(history)[-8:]", SERVER_SOURCE)
        self.assertIn('messages.append({"role": "user", "content": current_message})', SERVER_SOURCE)


if __name__ == "__main__":
    unittest.main()
