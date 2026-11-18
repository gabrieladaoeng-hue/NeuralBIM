import boto3
sts = boto3.client("sts", region_name="us-east-2")
identity = sts.get_caller_identity()
print("Autenticado com sucesso!")
print("Conta:", identity["Account"])
print("Usuario:", identity["Arn"])
