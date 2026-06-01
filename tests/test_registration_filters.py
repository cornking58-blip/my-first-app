import importlib.util
import os
import re
import sys
import types
import unittest
from pathlib import Path


def load_server_module():
    os.environ.setdefault("MONGO_URL", "mongodb://test")
    os.environ.setdefault("DB_NAME", "test")

    fastapi = types.ModuleType("fastapi")

    class DummyApp:
        def __init__(self, *args, **kwargs):
            pass

        def include_router(self, *args, **kwargs):
            pass

        def add_middleware(self, *args, **kwargs):
            pass

        def on_event(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

    class DummyRouter:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        post = get
        delete = get

    class DummyHTTPException(Exception):
        pass

    fastapi.FastAPI = DummyApp
    fastapi.APIRouter = DummyRouter
    fastapi.HTTPException = DummyHTTPException
    fastapi.UploadFile = object
    fastapi.File = lambda *args, **kwargs: None
    fastapi.Query = lambda default=None, **kwargs: default
    sys.modules["fastapi"] = fastapi

    cors = types.ModuleType("starlette.middleware.cors")
    cors.CORSMiddleware = object
    sys.modules["starlette"] = types.ModuleType("starlette")
    sys.modules["starlette.middleware"] = types.ModuleType("starlette.middleware")
    sys.modules["starlette.middleware.cors"] = cors

    motor = types.ModuleType("motor.motor_asyncio")

    class DummyMongoClient:
        def __init__(self, *args, **kwargs):
            pass

        def __getitem__(self, name):
            return types.SimpleNamespace()

        def close(self):
            pass

    motor.AsyncIOMotorClient = DummyMongoClient
    sys.modules["motor"] = types.ModuleType("motor")
    sys.modules["motor.motor_asyncio"] = motor

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv

    pydantic = types.ModuleType("pydantic")

    class DummyBaseModel:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    pydantic.BaseModel = DummyBaseModel
    pydantic.Field = lambda default=None, default_factory=None, **kwargs: (
        default_factory() if default_factory else default
    )
    sys.modules["pydantic"] = pydantic
    sys.modules["pandas"] = types.ModuleType("pandas")

    spec = importlib.util.spec_from_file_location(
        "server_for_registration_filter_tests", Path("backend/server.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = load_server_module()


def mongo_condition_matches(row, condition):
    if not condition:
        return True

    if "$and" in condition:
        return all(mongo_condition_matches(row, part) for part in condition["$and"])

    for field, rule in condition.items():
        value = str(row.get(field) or "")
        if "$regex" in rule:
            flags = re.IGNORECASE if "i" in rule.get("$options", "") else 0
            if not re.search(rule["$regex"], value, flags):
                return False
        elif value != rule:
            return False

    return True


class RegistrationFilterTests(unittest.TestCase):
    def test_normalize_search_text(self):
        self.assertEqual(
            server.normalize_search_text("  Ржавчина, Ёжик!!!  "),
            "ржавчина ежик",
        )

    def test_service_words_are_ignored(self):
        self.assertEqual(
            server.build_fuzzy_word_patterns("пшеница против ржавчины"),
            ["пш[её]ниц", "ржавчин"],
        )

    def assert_registration_match(self, culture, harmful_object, crop, target_object):
        condition = server.build_registration_filters(
            culture=culture,
            harmful_object=harmful_object,
        )
        self.assertTrue(
            mongo_condition_matches(
                {"crop": crop, "target_object": target_object},
                condition,
            ),
            msg=f"Expected {condition} to match crop={crop!r}, target={target_object!r}",
        )

    def test_requested_russian_ending_examples_match_registration_rows(self):
        self.assert_registration_match(
            "подсолнечник",
            "ржавчина",
            "подсолнечника",
            "ржавчины",
        )
        self.assert_registration_match(
            "пшеница",
            "черепашка",
            "озимая пшеница",
            "клоп вредная черепашка",
        )
        self.assert_registration_match(
            "подсолнечник",
            "подмаренник",
            "подсолнечник масличный",
            "подмаренник цепкий",
        )
        self.assert_registration_match(
            "пшеница",
            "гниль",
            "яровая пшеница",
            "корневые гнили",
        )

    def test_all_significant_words_must_be_present_in_the_same_field(self):
        condition = server.build_registration_filters(culture="озимая пшеница")
        self.assertTrue(
            mongo_condition_matches({"crop": "озимая мягкая пшеница"}, condition)
        )
        self.assertFalse(
            mongo_condition_matches({"crop": "яровая пшеница"}, condition)
        )


if __name__ == "__main__":
    unittest.main()
