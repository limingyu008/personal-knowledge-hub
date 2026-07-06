import chromadb
from chromadb.config import Settings

client = chromadb.HttpClient(
    host='112.91.142.193',
    port=18018,
    tenant='default_tenant',
    database='default_database',
    settings=Settings(
        chroma_client_auth_provider="chromadb.auth.token_authn.TokenAuthClientProvider",
        chroma_client_auth_credentials="4397e1549dab9a658b47f530d5f37cd83ebdbe13d8020fdf5fd9e4475a67a250"
    )
)

# 列出所有集合（已确认）
collections = client.list_collections()
print("所有集合：", collections)

# 使用名称获取集合
collection = client.get_collection("personal_knowledge_chunks")
print("集合数量：", collection.count())

# 查询前10条数据（空集合也可能）
results = collection.get(limit=10)
print("查询结果：", results)