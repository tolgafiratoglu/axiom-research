from axiom_research.mcp.literature.server import NAME, create_literature_server
from axiom_research.mcp.runner import build_asgi_app, port_from_env

__all__ = ["NAME", "main"]


def main() -> None:
    server = create_literature_server()
    app = build_asgi_app(server)
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=port_from_env())


if __name__ == "__main__":
    main()
