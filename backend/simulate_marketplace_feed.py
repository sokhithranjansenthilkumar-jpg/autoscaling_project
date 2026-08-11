import argparse
import random
import time

import requests

SOURCES = ("amazon", "flipkart")


def parse_args():
    parser = argparse.ArgumentParser(description="Push synthetic marketplace metrics to Django API.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="Django API base URL")
    parser.add_argument("--interval", type=float, default=3.0, help="Delay in seconds between rounds")
    parser.add_argument(
        "--rounds",
        type=int,
        default=0,
        help="Number of rounds to run. Use 0 for infinite loop",
    )
    return parser.parse_args()


def random_payload(source):
    return {
        "source": source,
        "users": random.randint(80, 800),
        "cpu": round(random.uniform(25, 95), 2),
        "memory": round(random.uniform(30, 92), 2),
        "latency": round(random.uniform(55, 350), 2),
        "instances": random.randint(1, 10),
    }


def push_metric(api_base, payload):
    response = requests.post(
        f"{api_base.rstrip('/')}/predict/marketplace/",
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def run_simulation(api_base, interval, rounds):
    round_count = 0
    while rounds == 0 or round_count < rounds:
        round_count += 1
        print(f"\nRound {round_count}")
        for source in SOURCES:
            payload = random_payload(source)
            try:
                data = push_metric(api_base, payload)
                print(
                    f"{source}: users={payload['users']} cpu={payload['cpu']} "
                    f"memory={payload['memory']} latency={payload['latency']} "
                    f"recommended={data.get('recommended_instances')}"
                )
            except requests.RequestException as exc:
                print(f"{source}: failed -> {exc}")
        time.sleep(max(0.25, interval))


def main():
    args = parse_args()
    try:
        run_simulation(args.api_base, args.interval, args.rounds)
    except KeyboardInterrupt:
        print("\nStopped by user.")


if __name__ == "__main__":
    main()
