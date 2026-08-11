from unittest.mock import patch
from django.test import TestCase, Client

from .models import MetricSnapshot, ScenarioPreset


class AutoscalingApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("autoscaling.views.load_model")
    @patch("autoscaling.views.predict_instances")
    def test_predict_marketplace_works(self, mock_predict_instances, mock_load_model):
        mock_load_model.return_value = object()
        mock_predict_instances.return_value = 5

        response = self.client.post(
            "/predict/marketplace/",
            data=(
                '{"source":"amazon","users":120,"cpu":74,'
                '"memory":62,"latency":110,"instances":3}'
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["source"], "amazon")
        self.assertEqual(payload["recommended_instances"], 5)
        self.assertEqual(payload["current_instances"], 3)
        self.assertEqual(payload["delta"], 2)
        self.assertEqual(payload["scaling"], "scale_up")
        self.assertEqual(payload["snapshot"]["memory"], 62.0)
        self.assertEqual(payload["snapshot"]["latency"], 110.0)

    @patch("autoscaling.views.load_model")
    @patch("autoscaling.views.predict_instances")
    def test_marketplace_status_returns_scale_direction(
        self, mock_predict_instances, mock_load_model
    ):
        mock_load_model.return_value = object()
        mock_predict_instances.return_value = 7

        MetricSnapshot.objects.create(
            active_users=220,
            cpu=83.0,
            memory=77.0,
            latency=205.0,
            current_instances=4,
            source="amazon",
        )

        response = self.client.get("/status/marketplaces/")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertIn("amazon", payload["status"])
        self.assertEqual(payload["status"]["amazon"]["scaling"], "scale_up")

    @patch("autoscaling.views.load_model")
    @patch("autoscaling.views.predict_instances")
    def test_predict_marketplace_uses_previous_recommendation_as_baseline_for_demo_autoscaling(
        self, mock_predict_instances, mock_load_model
    ):
        mock_load_model.return_value = object()
        mock_predict_instances.side_effect = [5, 5, 5]

        first = self.client.post(
            "/predict/marketplace/",
            data=(
                '{"source":"amazon","users":500,"cpu":88,'
                '"memory":80,"latency":210,"instances":1}'
            ),
            content_type="application/json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["scaling"], "scale_up")

        second = self.client.post(
            "/predict/marketplace/",
            data=(
                '{"source":"amazon","users":40,"cpu":15,'
                '"memory":22,"latency":55}'
            ),
            content_type="application/json",
        )

        self.assertEqual(second.status_code, 201)
        payload = second.json()
        self.assertEqual(payload["current_instances"], 5)
        self.assertEqual(payload["recommended_instances"], 5)
        self.assertEqual(payload["delta"], 0)
        self.assertEqual(payload["scaling"], "stable")

    @patch("autoscaling.views.load_model")
    @patch("autoscaling.views.predict_instances")
    def test_predict_marketplace_can_transition_to_scale_down_after_previous_scale_up(
        self, mock_predict_instances, mock_load_model
    ):
        mock_load_model.return_value = object()
        mock_predict_instances.side_effect = [5, 5, 2]

        first = self.client.post(
            "/predict/marketplace/",
            data=(
                '{"source":"amazon","users":500,"cpu":88,'
                '"memory":80,"latency":210,"instances":1}'
            ),
            content_type="application/json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["scaling"], "scale_up")

        second = self.client.post(
            "/predict/marketplace/",
            data=(
                '{"source":"amazon","users":40,"cpu":15,'
                '"memory":22,"latency":55}'
            ),
            content_type="application/json",
        )

        self.assertEqual(second.status_code, 201)
        payload = second.json()
        self.assertEqual(payload["current_instances"], 5)
        self.assertEqual(payload["recommended_instances"], 2)
        self.assertEqual(payload["delta"], -3)
        self.assertEqual(payload["scaling"], "scale_down")

    @patch("autoscaling.views.load_model")
    @patch("autoscaling.views.predict_instances")
    def test_predict_marketplace_prefers_explicit_instances_when_provided(
        self, mock_predict_instances, mock_load_model
    ):
        mock_load_model.return_value = object()
        mock_predict_instances.side_effect = [5, 2]

        first = self.client.post(
            "/predict/marketplace/",
            data=(
                '{"source":"amazon","users":500,"cpu":88,'
                '"memory":80,"latency":210,"instances":1}'
            ),
            content_type="application/json",
        )
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            "/predict/marketplace/",
            data=(
                '{"source":"amazon","users":40,"cpu":15,'
                '"memory":22,"latency":55,"instances":4}'
            ),
            content_type="application/json",
        )

        self.assertEqual(second.status_code, 201)
        payload = second.json()
        self.assertEqual(payload["current_instances"], 4)
        self.assertEqual(payload["recommended_instances"], 2)
        self.assertEqual(payload["delta"], -2)
        self.assertEqual(payload["scaling"], "scale_down")

    def test_predict_requires_all_model_inputs(self):
        response = self.client.post(
            "/predict/",
            data='{"users":120,"cpu":74}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Missing 'memory' in request body")

    def test_predict_rejects_invalid_numeric_input(self):
        response = self.client.post(
            "/predict/",
            data='{"users":120,"cpu":"high","memory":74,"latency":110}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "'cpu' must be a valid float")

    def test_api_overview_lists_routes(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["service"], "autoscaling-api")
        self.assertIn("predict", payload["routes"])

    def test_scenario_presets_endpoint_returns_seeded_sqlite_rows(self):
        response = self.client.get("/scenario-presets/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertIn("Quiet traffic", payload["groups"])
        self.assertEqual(payload["count"], 50)
        self.assertEqual(payload["groups"]["Quiet traffic"][0]["row_number"], 1)
