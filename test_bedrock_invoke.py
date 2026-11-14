import boto3

client = boto3.client("bedrock-runtime", region_name="us-east-2")

response = client.converse(
    modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    messages=[
        {"role": "user", "content": [{"text": "Responda em uma frase: o que e BIM na construcao civil?"}]}
    ],
)

print(response["output"]["message"]["content"][0]["text"])
