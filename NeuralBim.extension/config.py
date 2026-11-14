# -*- coding: utf-8 -*-
"""
NeuralBIM - Configuração de Ambiente
Define variáveis de ambiente para a extensão pyRevit.
"""
import os

# Define o caminho para o arquivo de credenciais AWS
# Isso garante que o boto3 encontre as credenciais mesmo no ambiente do Revit.
os.environ['AWS_SHARED_CREDENTIALS_FILE'] = r"C:\Users\GABRI\.aws\credentials"

# Você pode adicionar outras variáveis de ambiente aqui se precisar no futuro.
# Exemplo: os.environ['MEU_TOKEN_API'] = 'SEU_TOKEN'
