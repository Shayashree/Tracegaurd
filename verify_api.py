"""Live API Verification Script."""
import time
import httpx
import uvicorn
import threading
from backend.main import app

def run_server(server):
    server.run()

def main():
    config = uvicorn.Config(app, host="127.0.0.1", port=8008, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    thread.start()

    time.sleep(1.5)  # Wait for server to start

    client = httpx.Client(base_url="http://127.0.0.1:8008", timeout=10.0)

    print("\n--- 1. Testing GET /health ---")
    resp = client.get("/health")
    print(f"Status: {resp.status_code}, Body: {resp.json()}")
    assert resp.status_code == 200

    print("\n--- 2. Testing POST /tasks ---")
    payload = {
        "task": "Find the prices of Product A and Product B, then calculate their combined price.",
        "verification_rule": {
            "type": "numerical_tolerance",
            "expected_value": 130.0,
            "tolerance": 0.01
        }
    }
    resp = client.post("/tasks", json=payload)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    task_id = data["task_id"]
    print(f"Created Task ID: {task_id}")
    print(f"Final Answer   : {data['final_answer']}")
    print(f"Verification   : {data['verification']}")
    assert resp.status_code == 201

    print(f"\n--- 3. Testing GET /tasks/{task_id} ---")
    resp = client.get(f"/tasks/{task_id}")
    print(f"Status: {resp.status_code}, Task Status: {resp.json()['status']}")
    assert resp.status_code == 200

    print(f"\n--- 4. Testing GET /tasks/{task_id}/traces ---")
    resp = client.get(f"/tasks/{task_id}/traces")
    print(f"Status: {resp.status_code}, Event Count: {len(resp.json())}")
    assert resp.status_code == 200

    print(f"\n--- 5. Testing GET /tasks/{task_id}/traces/export ---")
    resp = client.get(f"/tasks/{task_id}/traces/export")
    print(f"Status: {resp.status_code}, Content-Type: {resp.headers.get('content-type')}")
    print(f"JSONL Preview (first 2 lines):\n" + "\n".join(resp.text.strip().splitlines()[:2]))
    assert resp.status_code == 200

    print("\nAll live HTTP endpoints verified successfully!")
    server.should_exit = True

if __name__ == "__main__":
    main()
