import chromadb
# 创建 HTTP 客户端连接
client = chromadb.HttpClient(host='localhost', port=8018)
# 发送心跳并打印版本
print(f"心跳响应: {client.heartbeat()}")
print(f"ChromaDB 版本: {client.get_version()}")