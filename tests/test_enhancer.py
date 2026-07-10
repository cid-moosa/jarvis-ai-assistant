import sys
import os
import pytest
from flask import Flask
from pydantic import ValidationError

# Ensure root directory is on python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.server import app, EnhanceRequest
from core.enhancer import PromptEnhancer

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_serve_index(client):
    """
    Test that the root URL successfully serves the HTML frontend.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "JARVIS" in response.text

def test_api_enhance_local(client):
    """
    Test the API endpoint with local heuristic mode.
    """
    payload = {
        "prompt": "write a function to fetch web pages",
        "detail_level": "concise",
        "tone": "casual",
        "use_llm": False
    }
    response = client.post("/api/enhance", json=payload)
    assert response.status_code == 200
    
    data = response.get_json()
    assert data["original"] == payload["prompt"]
    assert "Role" in data["enhanced"]
    assert "Task" in data["enhanced"]
    assert "Write a function to fetch web pages" in data["enhanced"]
    assert data["method"] == "local"

def test_api_enhance_empty_prompt(client):
    """
    Test validation of the API payload with empty prompt.
    """
    payload = {
        "prompt": "",
        "use_llm": False
    }
    response = client.post("/api/enhance", json=payload)
    # Pydantic validation error returns 422
    assert response.status_code == 422

def test_local_enhancer_role_inference():
    """
    Test that the local heuristic correctly infers roles.
    """
    enhancer = PromptEnhancer()
    
    # Software engineer role
    role_se = enhancer._infer_role("write a python script to parse logs")
    assert "Software Engineer" in role_se
    
    # Copywriter role
    role_cw = enhancer._infer_role("write a blog post about artificial intelligence")
    assert "Copywriter" in role_cw
    
    # Generic role fallback
    role_generic = enhancer._infer_role("do something interesting")
    assert "Subject Matter Expert" in role_generic

def test_api_enhance_advanced_local(client):
    """
    Test the API endpoint with advanced options in local mode.
    """
    payload = {
        "prompt": "build a key-value store",
        "detail_level": "detailed",
        "tone": "professional",
        "use_llm": False,
        "archetype": "developer_agent",
        "include_rules": ["minimal_complexity", "output_efficiency"],
        "tools_list": ["read_file", "write_file"]
    }
    response = client.post("/api/enhance", json=payload)
    assert response.status_code == 200
    
    data = response.get_json()
    enhanced = data["enhanced"]
    
    # Check archetype role assignment
    assert "Role: Senior Software Engineering Agent" in enhanced
    
    # Check tools listing
    assert "Tools & Execution" in enhanced
    assert "read_file" in enhanced
    assert "write_file" in enhanced
    
    # Check rule inclusion
    assert "premature abstraction" in enhanced  # minimal_complexity text fragment
    assert "simplest approach first" in enhanced # output_efficiency text fragment

def test_local_enhancer_archetypes():
    """
    Test that archetypes are correctly mapped to roles in local mode.
    """
    enhancer = PromptEnhancer()
    
    # General
    enhanced_gen = enhancer._enhance_local("test", "concise", "professional", "general", None, None)
    assert "Role: Subject Matter Expert" in enhanced_gen
    
    # Developer Agent
    enhanced_dev = enhancer._enhance_local("test", "concise", "professional", "developer_agent", None, None)
    assert "Role: Senior Software Engineering Agent" in enhanced_dev
    
    # TUI Assistant
    enhanced_tui = enhancer._enhance_local("test", "concise", "professional", "tui_assistant", None, None)
    assert "Role: Interactive Terminal UI Assistant" in enhanced_tui
