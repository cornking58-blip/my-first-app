import unittest

from backend import sitecustomize as enhancer


class AIRuntimeEnhancerTest(unittest.TestCase):
    def test_agroexpert_seed_treatment_catalog_is_detected(self):
        message = "Выпиши все протравители от Agroexpert Group"
        self.assertTrue(enhancer._is_company_catalog_request(message))
        prompt = enhancer._research_prompt(message)
        self.assertIn("agroex.ru", prompt)
        self.assertIn("перечисли все найденные продукты", prompt)
        self.assertIn("официальный каталог", prompt)

    def test_product_comparison_gets_separate_fact_check(self):
        message = "Сравни Крестраж с Флинт на пшенице против снежной плесени"
        self.assertTrue(enhancer._is_product_research_request(message))
        prompt = enhancer._research_prompt(message)
        self.assertIn("Для каждого препарата отдельно", prompt)
        self.assertIn("Не смешивай болезни по вегетации", prompt)
        self.assertIn("полезный агрономический вывод", prompt)

    def test_field_advisor_tone_is_human_but_safe(self):
        prompt = enhancer._field_advisor_prompt()
        self.assertIn("товарищ-агроном", prompt)
        self.assertIn("лёгкая полевая шутка", prompt)
        self.assertIn("не в вопросах безопасности", prompt)
        self.assertIn("не ограничивайся отказом", prompt)

    def test_source_urls_are_appended_without_duplicates(self):
        sources = [
            {"title": "Каталог", "url": "https://agroex.ru/catalog/"},
            {"title": "Дубликат", "url": "https://agroex.ru/catalog/"},
        ]
        answer = enhancer._append_sources("Ответ", sources)
        self.assertEqual(answer.count("https://agroex.ru/catalog/"), 2)
        answer_again = enhancer._append_sources(answer, sources)
        self.assertEqual(answer_again.count("https://agroex.ru/catalog/"), 2)


if __name__ == "__main__":
    unittest.main()
