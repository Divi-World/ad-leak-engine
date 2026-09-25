"""Swarm task distribution for the Distributed Ephemeral Swarm [SEED: 2399]."""


class SwarmDispatcher:
    """Plans batches and generates GitHub Actions dispatch commands."""

    def plan_batches(self, keywords: list[str], shards: int) -> list[list[str]]:
        """Distribute keywords across shards via round-robin."""
        if shards <= 0:
            raise ValueError("shards must be > 0")
        batches = [[] for _ in range(shards)]
        for i, kw in enumerate(keywords):
            batches[i % shards].append(kw)
        return batches

    def generate_dispatch_commands(self, keyword: str, country: str, runs: int = 1) -> list[str]:
        """Generate `gh workflow run` commands to trigger the swarm."""
        return [
            f'gh workflow run swarm_matrix.yml -f keyword="{keyword}" -f country="{country}"'
            for _ in range(runs)
        ]

    def estimate_runner_load(self, runs: int, shards_per_run: int = 5) -> dict:
        """Estimate GitHub Actions minute usage against the free tier."""
        total_runners = runs * shards_per_run
        minutes_per_runner = 6
        total_minutes = total_runners * minutes_per_runner
        return {
            "total_runners": total_runners,
            "estimated_minutes": total_minutes,
            "within_free_tier": total_minutes <= 2000,
        }
