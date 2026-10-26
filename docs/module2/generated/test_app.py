import sys
import pathlib
import json

# Add the current directory to sys.path for local imports
sys.path.append(str(pathlib.Path(__file__).resolve().parent))

from app import app

def test_health_endpoint():
    with app.test_client() as client:
        response = client.get('/health')
        assert response.status_code == 200
        assert response.is_json
        assert response.get_json() == {'status': 'ok'}

def test_echo_endpoint():
    with app.test_client() as client:
        # Test valid JSON object
        response = client.post('/echo', json={'message': 'hello', 'count': 2})
        assert response.status_code == 200
        assert response.is_json
        assert response.get_json() == {'message': 'hello', 'count': 2}

        # Test nested JSON object
        response = client.post('/echo', json={'nested': {'items': [1, True, None]}})
        assert response.status_code == 200
        assert response.is_json
        assert response.get_json() == {'nested': {'items': [1, True, None]}}

        # Test empty JSON object
        response = client.post('/echo', json={})
        assert response.status_code == 200
        assert response.is_json
        assert response.get_json() == {}

        # Test malformed JSON
        response = client.post('/echo', data='{broken', content_type='application/json')
        assert response.status_code == 400

        # Test non-object JSON (array)
        response = client.post('/echo', json=[1, 2])
        assert response.status_code == 400

        # Test non-object JSON (null)
        response = client.post('/echo', data='null', content_type='application/json')
        assert response.status_code == 400

        # Test wrong content type
        response = client.post('/echo', data='hello', content_type='text/plain')
        assert response.status_code == 415

if __name__ == '__main__':
    test_health_endpoint()
    print('GET /health endpoint test passed.')
    test_echo_endpoint()
    print('POST /echo endpoint tests passed.')
