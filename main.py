import asyncio

import typer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import (
    GroupAuthorizationFailedError,
    GroupIdNotFound,
    TopicAlreadyExistsError,
    UnknownTopicOrPartitionError,
)

_default_bootstrap_servers = "kafka-server.orb.local:9092"
app = typer.Typer(help="Kafka Management CLI Tool")


def _create_admin_client(bootstrap_servers: str) -> AIOKafkaAdminClient:
    return AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)


async def _execute_admin_operation(func, *args, **kwargs):
    admin = None
    try:
        admin = _create_admin_client(kwargs.get("bootstrap_servers"))
        await admin.start()
        return await func(admin, *args, **kwargs)
    finally:
        if admin:
            await admin.close()


@app.command()
def create_topic(
    topic: str,
    partitions: int = typer.Option(..., min=1, help="Number of partitions"),
    replication_factor: int = typer.Option(1, min=1, help="Replication factor"),
    bootstrap_servers: str = typer.Option(
        _default_bootstrap_servers, help="Kafka broker addresses (comma separated)"
    ),
):
    """Create a new topic in Kafka"""
    asyncio.run(
        _execute_admin_operation(
            _create_topic,
            topic,
            partitions,
            replication_factor,
            bootstrap_servers=bootstrap_servers,
        )
    )


async def _create_topic(
    admin: AIOKafkaAdminClient,
    topic: str,
    partitions: int,
    replication_factor: int,
    **kwargs,
):
    try:
        await admin.create_topics(
            [
                NewTopic(
                    name=topic,
                    num_partitions=partitions,
                    replication_factor=replication_factor,
                )
            ]
        )
        typer.echo(f"Topic '{topic}' created successfully")
    except TopicAlreadyExistsError:
        typer.echo(f"Error: Topic '{topic}' already exists!", err=True)
        raise typer.Exit(code=1)


@app.command()
def list_topics(
    bootstrap_servers: str = typer.Option(
        _default_bootstrap_servers, help="Kafka broker addresses (comma separated)"
    ),
):
    """List all topics in Kafka"""
    asyncio.run(
        _execute_admin_operation(_list_topics, bootstrap_servers=bootstrap_servers)
    )


async def _list_topics(admin: AIOKafkaAdminClient, **kwargs):
    try:
        topics = await admin.list_topics()
        typer.echo("Available topics:")
        for topic in sorted(topics):
            typer.echo(f"  - {topic}")
    except Exception as e:
        typer.echo(f"Error listing topics: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def describe_topic(
    topic: str,
    bootstrap_servers: str = typer.Option(
        _default_bootstrap_servers, help="Kafka broker addresses (comma separated)"
    ),
):
    """Describe a topic's details"""
    asyncio.run(
        _execute_admin_operation(
            _describe_topic, topic, bootstrap_servers=bootstrap_servers
        )
    )


async def _describe_topic(admin: AIOKafkaAdminClient, topic: str, **kwargs):
    try:
        desc = await admin.describe_topics([topic])
        desc = desc[0]
        typer.echo(f"Topic:       {topic}")
        typer.echo(f"Error Code:  {desc.get('error_code', 0)}")
        typer.echo(f"Is Internal: {desc.get('is_internal', False)}")
        typer.echo(f"Partitions:  {len(desc.get('partitions', []))}")
        for partition in desc.get("partitions", []):
            typer.echo(f"  Partition:  {partition.get('partition', 0)}")
            typer.echo(f"  Error Code: {partition.get('error_code', 0)}")
            typer.echo(f"  Leader:     {partition.get('leader', 0)}")
            typer.echo(f"  Replicas:   {partition.get('replicas', [])}")
            typer.echo(f"  Isr:        {partition.get('isr', [])}")
            typer.echo("---")

    except Exception as e:
        typer.echo(f"Error describing topic: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def delete_topic(
    topic: str,
    bootstrap_servers: str = typer.Option(
        _default_bootstrap_servers, help="Kafka broker addresses (comma separated)"
    ),
):
    """Delete a topic from Kafka"""
    asyncio.run(
        _execute_admin_operation(
            _delete_topic, topic, bootstrap_servers=bootstrap_servers
        )
    )


async def _delete_topic(admin: AIOKafkaAdminClient, topic: str, **kwargs):
    try:
        await admin.delete_topics([topic])
        typer.echo(f"Topic '{topic}' deleted successfully")
    except UnknownTopicOrPartitionError:
        typer.echo(f"Error: Topic '{topic}' does not exist!", err=True)
        raise typer.Exit(code=1)


@app.command()
def list_groups(
    bootstrap_servers: str = typer.Option(
        _default_bootstrap_servers, help="Kafka broker addresses (comma separated)"
    ),
):
    """List all consumer groups"""
    asyncio.run(
        _execute_admin_operation(_list_groups, bootstrap_servers=bootstrap_servers)
    )


async def _list_groups(admin: AIOKafkaAdminClient, **kwargs):
    try:
        groups = await admin.list_consumer_groups()
        typer.echo("Consumer Groups:")
        for group_id, protocol_type in groups:
            typer.echo(f"  - {group_id=}, {protocol_type=}")
    except Exception as e:
        typer.echo(f"Error listing consumer groups: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def describe_group(
    group_id: str = typer.Argument(..., help="Consumer group ID to describe"),
    bootstrap_servers: str = typer.Option(
        _default_bootstrap_servers, help="Kafka broker addresses (comma separated)"
    ),
):
    """Describe a consumer group's details"""
    asyncio.run(
        _execute_admin_operation(
            _describe_group, group_id, bootstrap_servers=bootstrap_servers
        )
    )


async def _describe_group(admin: AIOKafkaAdminClient, group_id: str, **kwargs):
    try:
        descriptions = await admin.describe_consumer_groups([group_id])
        desc = descriptions[0]

        if isinstance(desc, Exception):
            raise desc

        if not hasattr(desc, "groups") or not desc.groups or len(desc.groups) == 0:
            typer.echo(f"Error: Consumer group '{group_id}' not found!", err=False)
            raise typer.Exit(code=0)

        for group in desc.groups:
            error_code, group_name, state, protocol_type, protocol, members = group
            typer.echo(f"Error Code:      {error_code}")
            typer.echo(f"Group ID:        {group_name}")
            typer.echo(f"State:           {state}")
            typer.echo(f"Protocol Type:   {protocol_type}")
            typer.echo(f"Protocol:        {protocol}")
            typer.echo("Members:")

            for member in members:
                print(member)
            #     typer.echo(f"\n  Member ID:     {member.member_id}")
            #     typer.echo(f"  Client ID:     {member.client_id}")
            #     typer.echo(f"  Client Host:   {member.client_host}")
            #     typer.echo("  Assignments:")

    except GroupIdNotFound:
        typer.echo(f"Error: Consumer group '{group_id}' not found!", err=True)
        raise typer.Exit(code=1)
    except GroupAuthorizationFailedError:
        typer.echo(f"Error: Not authorized to describe group '{group_id}'!", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error describing group: {e}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
