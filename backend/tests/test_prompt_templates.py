"""Tests for prompt templates API."""
import httpx

BASE_URL = "http://localhost:8000/api/replies"


def cleanup_test_templates():
    """Remove all non-default templates."""
    response = httpx.get(f"{BASE_URL}/prompt-templates")
    if response.status_code == 200:
        templates = response.json().get("templates", [])
        for t in templates:
            if not t.get("is_default") and t.get("id"):
                httpx.delete(f"{BASE_URL}/prompt-templates/{t['id']}")


def test_list_templates():
    """Test listing prompt templates."""
    response = httpx.get(f"{BASE_URL}/prompt-templates")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "templates" in data, "Response missing 'templates' key"
    defaults = [t for t in data["templates"] if t.get("is_default")]
    assert len(defaults) >= 1, "Should have at least one default template"


def test_create_template_minimal():
    """Test creating a template with minimal fields (no prompt_type)."""
    payload = {
        "name": "Test Template Simple",
        "prompt_text": "This is a test prompt",
        "is_default": False
    }
    response = httpx.post(f"{BASE_URL}/prompt-templates", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["name"] == "Test Template Simple"
    assert data["prompt_text"] == "This is a test prompt"
    assert data["is_default"] == False
    
    # Cleanup
    if data.get("id"):
        httpx.delete(f"{BASE_URL}/prompt-templates/{data['id']}")


def test_create_template_with_type():
    """Test creating a template with optional prompt_type."""
    payload = {
        "name": "Test Classification",
        "prompt_text": "Classify this email",
        "prompt_type": "classification",
        "is_default": False
    }
    response = httpx.post(f"{BASE_URL}/prompt-templates", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["prompt_type"] == "classification"
    
    # Cleanup
    if data.get("id"):
        httpx.delete(f"{BASE_URL}/prompt-templates/{data['id']}")


def test_update_template():
    """Test updating a template."""
    # Create
    payload = {"name": "Update Test", "prompt_text": "Original", "is_default": False}
    create_resp = httpx.post(f"{BASE_URL}/prompt-templates", json=payload)
    assert create_resp.status_code == 200
    template_id = create_resp.json()["id"]
    
    # Update
    update_payload = {"name": "Updated Name", "prompt_text": "Updated text", "is_default": False}
    update_resp = httpx.put(f"{BASE_URL}/prompt-templates/{template_id}", json=update_payload)
    assert update_resp.status_code == 200
    
    # Verify
    list_resp = httpx.get(f"{BASE_URL}/prompt-templates")
    templates = list_resp.json()["templates"]
    updated = next((t for t in templates if t["id"] == template_id), None)
    assert updated is not None, "Updated template not found"
    assert updated["name"] == "Updated Name"
    
    # Cleanup
    httpx.delete(f"{BASE_URL}/prompt-templates/{template_id}")


def test_delete_template():
    """Test deleting a template."""
    # Create
    payload = {"name": "Delete Test", "prompt_text": "To be deleted", "is_default": False}
    create_resp = httpx.post(f"{BASE_URL}/prompt-templates", json=payload)
    assert create_resp.status_code == 200
    template_id = create_resp.json()["id"]
    
    # Delete
    delete_resp = httpx.delete(f"{BASE_URL}/prompt-templates/{template_id}")
    assert delete_resp.status_code == 200
    
    # Verify deleted
    list_resp = httpx.get(f"{BASE_URL}/prompt-templates")
    templates = list_resp.json()["templates"]
    assert not any(t["id"] == template_id for t in templates), "Template should be deleted"


def run_all_tests():
    """Run all tests and return results."""
    print("\n=== Prompt Templates API Tests ===")
    
    # Cleanup first
    print("Cleaning up test templates...")
    cleanup_test_templates()
    
    tests = [
        ("list_templates", test_list_templates),
        ("create_template_minimal", test_create_template_minimal),
        ("create_template_with_type", test_create_template_with_type),
        ("update_template", test_update_template),
        ("delete_template", test_delete_template),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            test_fn()
            print(f"✅ {name}: PASS")
            passed += 1
        except AssertionError as e:
            print(f"❌ {name}: FAIL - {e}")
            failed += 1
        except Exception as e:
            print(f"⚠️ {name}: ERROR - {e}")
            failed += 1
    
    # Final cleanup
    print("\nFinal cleanup...")
    cleanup_test_templates()
    
    print(f"\n=== Results: {passed}/{passed + failed} passed ===")
    return passed, failed


if __name__ == "__main__":
    passed, failed = run_all_tests()
    exit(0 if failed == 0 else 1)
