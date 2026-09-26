import argparse
import asyncio
import json

from .cutover_service import CutoverService
from .infrai_dns import InfraiDnsClient
from .models import CutoverRequest


async def run(args: argparse.Namespace) -> None:
    dns = InfraiDnsClient()
    try:
        result = await CutoverService(dns).release(
            CutoverRequest(
                domain=args.domain,
                name=args.name,
                record_type=args.type,
                content=args.content,
                ttl=args.ttl,
                build_id=args.build_id,
            )
        )
        print(json.dumps(result.model_dump(mode="json"), indent=2))
    finally:
        await dns.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Release a developer-tools DNS cutover")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--type", choices=["A", "CNAME"], required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--ttl", type=int, default=60)
    parser.add_argument("--build-id", required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
