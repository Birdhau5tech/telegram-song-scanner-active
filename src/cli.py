"""Command-line interface for the Song Scanner."""

import click

from config.database import SessionLocal
from src.core.state_manager import state_manager
from src.database.models import SongRequest
from src.database.operations import ChatOperations, RequestOperations
from src.radiodj_integration.sync_service import sync_service
from src.utils.logger import get_logger

logger = get_logger(__name__)


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Song Scanner CLI - Manage song requests to RadioDJ."""


@cli.command()
@click.option(
    "--limit",
    default=50,
    type=int,
    help="Maximum requests to sync",
)
def sync(limit):
    """Sync approved song requests to RadioDJ.

    Examples:
        python -m src.cli sync              # Sync up to 50 requests
        python -m src.cli sync --limit=10   # Sync up to 10 requests
    """
    db = SessionLocal()
    try:
        click.echo(f"Syncing approved requests (limit: {limit})...")
        stats = sync_service.sync_approved_requests(db, limit)
        click.echo("✓ Sync completed:")
        click.echo(f"  - Synced: {stats['synced']}")
        click.echo(f"  - Failed: {stats['failed']}")
        state_manager.update_last_sync()
    except (RuntimeError, ValueError, OSError, KeyError, AttributeError) as e:
        click.echo(f"✗ Error during sync: {e}", err=True)
        logger.error("Sync error: %s", e)
    finally:
        db.close()


@cli.command()
def status():
    """Show current application status.

    Examples:
        python -m src.cli status
    """
    state = state_manager.get_state()
    uptime = state_manager.get_uptime_seconds()

    click.echo("\n" + "=" * 50)
    click.echo("Song Scanner Status")
    click.echo("=" * 50)
    click.echo(f"Status: {state.get('status', 'unknown')}")
    click.echo(f"Uptime: {uptime:.0f} seconds")
    click.echo(f"Started: {state.get('started_at', 'unknown')}")
    click.echo(f"Last scan: {state.get('last_scan', 'never')}")
    click.echo(f"Last sync: {state.get('last_sync', 'never')}")
    click.echo("\nStatistics:")
    stats = state.get("stats", {})
    for stat_name, value in stats.items():
        click.echo(f"  - {stat_name}: {value}")
    click.echo("=" * 50 + "\n")


@cli.command()
def list_chats():
    """List all active chats.

    Examples:
        python -m src.cli list-chats
    """
    db = SessionLocal()
    try:
        chats = ChatOperations.get_active_chats(db)
        if not chats:
            click.echo("No active chats found.")
            return

        click.echo(f"\nActive chats ({len(chats)}):")
        click.echo("-" * 60)
        for chat in chats:
            click.echo(f"  ID: {chat.chat_id}")
            click.echo(f"  Name: {chat.chat_name or 'Unknown'}")
            click.echo(f"  Last scan: {chat.last_scan_time or 'Never'}")
            click.echo()
    except (RuntimeError, ValueError, OSError, KeyError, AttributeError) as e:
        click.echo(f"✗ Error listing chats: {e}", err=True)
        logger.error("List chats error: %s", e)
    finally:
        db.close()


@cli.command()
@click.option("--limit", default=10, type=int, help="Maximum requests to display")
def list_requests(limit):
    """List pending song requests.

    Examples:
        python -m src.cli list-requests              # Show 10 pending requests
        python -m src.cli list-requests --limit=20   # Show 20 pending requests
    """
    db = SessionLocal()
    try:
        requests = RequestOperations.get_pending_requests(db, limit)
        if not requests:
            click.echo("No pending requests found.")
            return

        click.echo(f"\nPending requests ({len(requests)}):")
        click.echo("-" * 80)
        for req in requests:
            matched = req.matched_song
            artist = matched.artist_name if matched else "Unknown"
            title = matched.song_title if matched else "Unknown"
            click.echo(f"  ID: {req.id}")
            click.echo(f"  Song: {artist} - {title}")
            click.echo(f"  Requested by: {req.requested_by or 'Anonymous'}")
            click.echo(f"  Status: {req.status}")
            click.echo(f"  Created: {req.created_at}")
            click.echo()
    except (RuntimeError, ValueError, OSError, KeyError, AttributeError) as e:
        click.echo(f"✗ Error listing requests: {e}", err=True)
        logger.error("List requests error: %s", e)
    finally:
        db.close()


@cli.command()
@click.argument("request_id", type=int)
def approve(request_id):
    """Approve a song request.

    Examples:
        python -m src.cli approve 5
    """
    db = SessionLocal()
    try:
        request = db.query(SongRequest).filter(SongRequest.id == request_id).first()
        if not request:
            click.echo(f"✗ Request {request_id} not found.", err=True)
            return

        RequestOperations.approve_request(db, request_id)
        click.echo(f"✓ Request {request_id} approved.")
    except (RuntimeError, ValueError, OSError, KeyError, AttributeError) as e:
        click.echo(f"✗ Error approving request: {e}", err=True)
        logger.error("Approve request error: %s", e)
    finally:
        db.close()


@cli.command()
@click.argument("request_id", type=int)
@click.option("--notes", default="", help="Rejection notes")
def reject(request_id, notes):
    """Reject a song request.

    Examples:
        python -m src.cli reject 5
        python -m src.cli reject 5 --notes="Not available"
    """
    db = SessionLocal()
    try:
        RequestOperations.reject_request(db, request_id, notes)
        click.echo(f"✓ Request {request_id} rejected.")
    except (RuntimeError, ValueError, OSError, KeyError, AttributeError) as e:
        click.echo(f"✗ Error rejecting request: {e}", err=True)
        logger.error("Reject request error: %s", e)
    finally:
        db.close()


if __name__ == "__main__":
    cli()
