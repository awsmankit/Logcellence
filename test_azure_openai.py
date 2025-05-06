import yaml
import httpx
import asyncio

# Load OpenAI config from a yaml file
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

OPENAI_API_KEY = config["openai"]["api_key"]
OPENAI_API_VERSION = config["openai"]["api_version"]
OPENAI_ENDPOINT = config["openai"]["azure_endpoint_chat"]
OPENAI_DEPLOYMENT_ID = config["openai"]["deployment_id"]

async def test_azure_openai():
    print("Testing Azure OpenAI API connection...")
    print(f"Endpoint: {OPENAI_ENDPOINT}")
    print(f"Deployment ID: {OPENAI_DEPLOYMENT_ID}")
    print(f"API Version: {OPENAI_API_VERSION}")
    print(f"API Key: {OPENAI_API_KEY[:4]}{'*' * (len(OPENAI_API_KEY) - 8)}{OPENAI_API_KEY[-4:] if len(OPENAI_API_KEY) > 8 else ''}")
    
    payload = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Summarize this log: ERROR [2023-04-28 10:15:23] Database connection failed - timeout after 30s"}
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": OPENAI_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            url = f"{OPENAI_ENDPOINT}/openai/deployments/{OPENAI_DEPLOYMENT_ID}/chat/completions?api-version={OPENAI_API_VERSION}"
            print(f"Making request to: {url}")
            
            response = await client.post(
                url,
                json=payload,
                headers=headers,
            )
            
            if response.status_code == 200:
                data = response.json()
                print("\n✅ API Connection Successful!")
                print("\nResponse:")
                print(f"Status Code: {response.status_code}")
                print(f"Summary: {data['choices'][0]['message']['content']}")
                return True
            else:
                print(f"\n❌ API Request Failed with status code {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"\n❌ Error connecting to Azure OpenAI API: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_azure_openai())