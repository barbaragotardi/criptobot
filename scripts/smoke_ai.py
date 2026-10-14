"""Phase 0 smoke: Haiku schema support + gemini-embedding-2 dim/task_type. No feature code."""

import sys

sys.path.insert(0, ".")


def main() -> int:
    print("== Haiku via LiteLLM ==")
    try:
        import litellm
        model = "anthropic/claude-haiku-4-5-20251001"
        print("supports_response_schema:", litellm.supports_response_schema(model=model))
        from pydantic import BaseModel

        class Ping(BaseModel):
            model_config = {"extra": "forbid"}
            ok: bool = True

        resp = litellm.completion(
            model=model, messages=[{"role": "user", "content": 'Return {"ok": true}'}],
            response_format={"type": "json_object",
                             "response_schema": Ping.model_json_schema()},
            max_tokens=100, timeout=40,
        )
        print("haiku reply:", (resp.choices[0].message.content or "")[:200])
        print("cost:", end=" ")
        try:
            print(litellm.completion_cost(completion_response=resp))
        except Exception as e:
            print(f"n/a ({e})")
    except Exception as e:
        print(f"HAIKU FAIL: {e}")
        return 1
    print("\n== gemini-embedding-2 ==")
    try:
        from google import genai
        from google.genai import types
        client = genai.Client()
        res = client.models.embed_content(
            model="gemini-embedding-2", contents="What is the meaning of life?")
        v = list(res.embeddings[0].values)
        print("default dim:", len(v))
        res2 = client.models.embed_content(
            model="gemini-embedding-2", contents=["BTC breaks resistance", "Fed holds rates"],
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT",
                                            output_dimensionality=768))
        print("batch n:", len(res2.embeddings), "dim:", len(list(res2.embeddings[0].values)))
        r3 = client.models.embed_content(
            model="gemini-embedding-2", contents="Solana ETF news",
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY",
                                            output_dimensionality=768))
        print("query dim:", len(list(r3.embeddings[0].values)))
    except Exception as e:
        print(f"EMBED FAIL: {e}")
        return 1
    print("\nSMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
