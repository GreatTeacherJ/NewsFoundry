from fastapi import  APIRouter

router = APIRouter(tags=["chat"]) 

#crée un nouveau thread et retourne son id
@router.post("/chats")
def chat_completion(prompt:str):
    return {"content":"message reçu"}
