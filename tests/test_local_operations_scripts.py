from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_local_operations_scripts_have_valid_shell_syntax():
    for name in ("backup_postgres.sh", "configurar_backup_cron.sh", "validar_local.sh", "testar_restauracao_homologacao.sh"):
        script = ROOT / "scripts" / name
        assert script.exists()
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_backup_script_is_local_and_keeps_database_bytes_out_of_the_repository():
    script = (ROOT / "scripts" / "backup_postgres.sh").read_text()
    assert "docker compose exec -T db" in script
    assert "pg_dump" in script
    assert "gzip -9" in script
    assert "BACKUP_DIR" in script
    assert "curl" not in script


def test_cron_script_uses_a_durable_system_cron_entry():
    script = (ROOT / "scripts" / "configurar_backup_cron.sh").read_text()
    assert "/etc/cron.d/projmanager-postgres-backup" in script
    assert "RETENTION_DAYS" in script
    assert "CRON_SCHEDULE" in script


def test_homologation_restore_is_temporary_by_default():
    script = (ROOT / "scripts" / "testar_restauracao_homologacao.sh").read_text()
    assert "createdb" in script
    assert "dropdb" in script
    assert "KEEP_DB" in script
    assert "ON_ERROR_STOP=1" in script
    assert "POSTGRES_DB" not in script
