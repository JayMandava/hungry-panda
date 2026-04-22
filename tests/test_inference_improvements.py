"""
Inference Improvements Tests

These tests verify the backend behavior changes for inference optimization:
1. Max 2 LLM calls per recommendation request
2. Fallback path makes 0 additional LLM calls
3. Structured failure path doesn't re-enter LLM

Run with: pytest tests/test_inference_improvements.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from typing import Dict, Any

# Use anyio for async tests
pytestmark = pytest.mark.anyio


class TestInferenceCallCount:
    """Test that recommendation flow respects the max 2-call limit"""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client that tracks calls"""
        call_tracker = {
            "visual_analysis": 0,
            "structured_recommendation": 0,
            "caption_generation": 0,
            "hashtag_generation": 0,
        }
        
        def mock_analyze_visual_asset(*args, **kwargs):
            call_tracker["visual_analysis"] += 1
            return {
                "food_present": True,
                "dish_detected": "pasta",
                "meal_type": "dinner",
                "cuisine_type": "italian",
                "confidence": 0.85,
                "visual_summary": "A plate of pasta with sauce",
                "contradicts_user_text": False,
            }
        
        def mock_generate_post_recommendation(*args, **kwargs):
            call_tracker["structured_recommendation"] += 1
            return {
                "content_analysis": {
                    "category": "recipe_tutorial",
                    "dish_detected": "pasta",
                    "meal_type": "dinner",
                    "cuisine_type": "italian",
                    "format": "image",
                    "confidence": 0.85,
                },
                "caption_variants": [
                    {
                        "label": "Performance",
                        "caption": "Try this amazing pasta recipe! 🍝",
                        "why": "Strong engagement hook",
                    },
                    {
                        "label": "Story-led",
                        "caption": "Sunday dinner with family 🥰",
                        "why": "Builds emotional connection",
                    },
                ],
                "hashtag_variants": [
                    {
                        "label": "Broader Discovery",
                        "hashtags": ["food", "pasta", "italian"],
                        "why": "Maximizes reach",
                    },
                    {
                        "label": "Targeted Intent",
                        "hashtags": ["recipe", "homemade", "dinner"],
                        "why": "Better relevance",
                    },
                ],
                "optimal_time": {
                    "time": "18:00",
                    "reasoning": "Dinner planning time",
                    "timezone": "local",
                    "engagement_prediction": "high",
                },
                "strategy_notes": "Post about dinner time",
                "confidence_score": 0.82,
                "content_patterns": ["recipe_tutorial"],
            }
        
        def mock_generate_caption(*args, **kwargs):
            call_tracker["caption_generation"] += 1
            return "LLM generated caption"
        
        def mock_generate_hashtags(*args, **kwargs):
            call_tracker["hashtag_generation"] += 1
            return ["food", "recipe", "yummy"]
        
        return {
            "tracker": call_tracker,
            "analyze_visual_asset": mock_analyze_visual_asset,
            "generate_post_recommendation": mock_generate_post_recommendation,
            "generate_caption": mock_generate_caption,
            "generate_hashtags": mock_generate_hashtags,
        }
    
    async def test_normal_path_makes_exactly_two_llm_calls(self, mock_llm_client):
        """P0: Normal recommendation path should make exactly 2 LLM calls"""
        from analyzer.content_engine import analyze_and_recommend, reset_llm_call_counts
        
        reset_llm_call_counts()
        
        with patch("analyzer.content_engine.llm_analyze_visual_asset") as mock_visual, \
             patch("analyzer.content_engine.llm_generate_post_recommendation") as mock_rec:
            
            mock_visual.side_effect = mock_llm_client["analyze_visual_asset"]
            mock_rec.side_effect = mock_llm_client["generate_post_recommendation"]
            
            request_metrics = {}
            result = await analyze_and_recommend(
                content_id="test-123",
                filepath="/fake/path/pasta.jpg",
                user_caption="Delicious pasta",
                context="",
                _request_metrics=request_metrics,
            )
            
            # Assert exactly 2 LLM calls were made
            assert request_metrics["llm_calls"] == 2, \
                f"Expected 2 LLM calls, got {request_metrics['llm_calls']}"
            
            # Assert the calls were visual + structured
            assert mock_visual.call_count == 1, "Should call visual analysis once"
            assert mock_rec.call_count == 1, "Should call structured recommendation once"
    
    async def test_fallback_path_makes_zero_additional_llm_calls(self, mock_llm_client):
        """P0: When structured fails, fallback should make 0 additional LLM calls"""
        from analyzer.content_engine import analyze_and_recommend, reset_llm_call_counts
        
        reset_llm_call_counts()
        
        with patch("analyzer.content_engine.llm_analyze_visual_asset") as mock_visual, \
             patch("analyzer.content_engine.llm_generate_post_recommendation") as mock_rec, \
             patch("analyzer.content_engine.llm_generate_caption") as mock_caption, \
             patch("analyzer.content_engine.llm_generate_hashtags") as mock_hashtags:
            
            mock_visual.side_effect = mock_llm_client["analyze_visual_asset"]
            # Make structured recommendation fail
            mock_rec.side_effect = Exception("Structured generation failed")
            mock_caption.side_effect = mock_llm_client["generate_caption"]
            mock_hashtags.side_effect = mock_llm_client["generate_hashtags"]
            
            request_metrics = {}
            result = await analyze_and_recommend(
                content_id="test-456",
                filepath="/fake/path/pizza.jpg",
                user_caption="Pizza night",
                context="",
                _request_metrics=request_metrics,
            )
            
            # Assert only 1 LLM call was made (visual only, structured failed)
            assert request_metrics["llm_calls"] == 1, \
                f"Expected 1 LLM call in fallback, got {request_metrics['llm_calls']}"
            
            # Assert fallback did NOT call caption or hashtag generation
            assert mock_caption.call_count == 0, "Fallback should NOT call llm_generate_caption"
            assert mock_hashtags.call_count == 0, "Fallback should NOT call llm_generate_hashtags"
            
            # Assert we got a valid result from fallback
            assert result["recommendation_source"] in ["llm_fallback", "template"]
            assert result["suggested_caption"], "Fallback should produce a caption"
            assert result["suggested_hashtags"], "Fallback should produce hashtags"
    
    async def test_build_caption_variants_respects_use_llm_false(self):
        """P0: build_caption_variants with use_llm=False should not call LLM"""
        from analyzer.content_engine import ContentAnalyzer
        
        analyzer = ContentAnalyzer()
        
        with patch("analyzer.content_engine.llm_generate_caption") as mock_caption:
            mock_caption.return_value = "LLM caption"
            
            # Call with use_llm=False
            variants = analyzer.build_caption_variants(
                content_type={"meal_type": "dinner", "cuisine_type": "italian"},
                content_description="pasta",
                seed="test-seed",
                use_llm=False,
            )
            
            # Should NOT call LLM
            assert mock_caption.call_count == 0, "use_llm=False should prevent LLM call"
            
            # Should still return valid variants
            assert len(variants) == 2, "Should return 2 caption variants"
            assert all(v["caption"] for v in variants), "All variants should have captions"
    
    async def test_build_hashtag_variants_respects_use_llm_false(self):
        """P0: build_hashtag_variants with use_llm=False should not call LLM"""
        from analyzer.content_engine import ContentAnalyzer
        
        analyzer = ContentAnalyzer()
        
        with patch("analyzer.content_engine.llm_generate_hashtags") as mock_hashtags:
            mock_hashtags.return_value = ["food", "recipe"]
            
            # Call with use_llm=False
            variants = analyzer.build_hashtag_variants(
                content_type={"meal_type": "dinner", "cuisine_type": "italian"},
                content_description="pasta",
                seed="test-seed",
                use_llm=False,
            )
            
            # Should NOT call LLM
            assert mock_hashtags.call_count == 0, "use_llm=False should prevent LLM call"
            
            # Should still return valid variants
            assert len(variants) == 2, "Should return 2 hashtag variants"
            assert all(v["hashtags"] for v in variants), "All variants should have hashtags"
    
    async def test_no_second_vision_pass_called(self, mock_llm_client):
        """P0: Visual analysis should NOT call second detail pass"""
        from integrations.llm_client import LLMClient
        
        client = LLMClient(provider="fireworks")
        
        with patch.object(client, "_call_llm") as mock_call, \
             patch.object(client, "_build_image_data_url") as mock_url:
            
            mock_url.return_value = "data:image/jpeg;base64,fake"
            # First call returns basic analysis
            mock_call.return_value = """
FOOD_PRESENT=yes
PRIMARY_SUBJECT=pasta
DISH=pasta
MEAL_TYPE=dinner
CUISINE=italian
CONFIDENCE=0.85
MISMATCH=no
SUMMARY=A plate of pasta
"""
            
            with patch.object(client, "_inspect_visual_detail") as mock_detail:
                mock_detail.return_value = "Detailed description"
                
                result = client._inspect_visual_asset(
                    "/fake/path.jpg",
                    user_caption=None,
                    context=None,
                )
                
                # Should NOT call _inspect_visual_detail
                assert mock_detail.call_count == 0, "Second vision pass should NOT be called"


class TestStageTimingMetrics:
    """Test that stage timing is properly recorded"""
    
    def test_stage_timer_records_duration(self):
        """StageTimer should record and log stage duration"""
        from analyzer.content_engine import StageTimer, STAGE_TIMINGS, get_stage_timings
        import time
        
        # Clear previous timings for this test
        STAGE_TIMINGS.clear()
        
        with StageTimer("test_stage"):
            time.sleep(0.01)  # 10ms
        
        timings = get_stage_timings()
        assert "test_stage" in timings, "Stage should be recorded"
        assert timings["test_stage"]["avg_ms"] >= 10, "Should record at least 10ms"
    
    def test_llm_call_count_tracking(self):
        """LLM call counts should be tracked correctly"""
        from analyzer.content_engine import (
            increment_llm_call_count,
            get_llm_call_counts,
            reset_llm_call_counts,
        )
        
        reset_llm_call_counts()
        
        # Increment some counts
        increment_llm_call_count("visual_analysis")
        increment_llm_call_count("visual_analysis")
        increment_llm_call_count("structured_recommendation")
        
        counts = get_llm_call_counts()
        assert counts["visual_analysis"] == 2, "Should track 2 visual analysis calls"
        assert counts["structured_recommendation"] == 1, "Should track 1 structured call"


class TestInferenceMetricsEndpoint:
    """Test that metrics are exposed via API"""
    
    async def test_health_endpoint_includes_inference_metrics(self):
        """Health endpoint should include inference metrics"""
        try:
            from backend.main import app
            from fastapi.testclient import TestClient
            client = TestClient(app)
        except (ImportError, RuntimeError, TypeError) as e:
            pytest.skip(f"Test client not available: {e}")
        
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "inference_metrics" in data, "Health should include inference_metrics"
        metrics = data["inference_metrics"]
        
        # Check required fields
        assert "stage_timings" in metrics, "Should include stage_timings"
        assert "llm_call_counts" in metrics, "Should include llm_call_counts"
        assert "recommendation_stats" in metrics, "Should include recommendation_stats"
    
    async def test_debug_inference_metrics_endpoint(self):
        """Debug endpoint should return detailed inference metrics"""
        try:
            from backend.main import app
            from fastapi.testclient import TestClient
            client = TestClient(app)
        except (ImportError, RuntimeError, TypeError) as e:
            pytest.skip(f"Test client not available: {e}")
        
        response = client.get("/api/debug/inference-metrics")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "stage_timings" in data, "Should include stage_timings"
        assert "llm_call_counts" in data, "Should include llm_call_counts"
        assert "recommendation_stats" in data, "Should include recommendation_stats"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
