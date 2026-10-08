import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from concurrent.futures import ThreadPoolExecutor
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from livelife.ssh_transport import CourseSSH


def result(code=0, out="", error=""):
    return subprocess.CompletedProcess([], code, out, error)


class SSHTransportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir="/tmp")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.key = self.root / "key"
        self.hosts = self.root / "hosts"
        self.key.write_text("test credential placeholder")
        self.hosts.write_text("test host placeholder")
        self.command = [
            "ssh",
            "-T",
            "-i",
            str(self.key),
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "UserKnownHostsFile=" + str(self.hosts),
        ]
        self.transport = CourseSSH(self.root, self.command, "group5@example.test")

    def test_authenticated_master_reused_without_network_fallback(self):
        with patch(
            "livelife.ssh_transport.subprocess.run",
            side_effect=[result(), result(out='{"ready":true}')],
        ) as run:
            self.assertEqual(
                self.transport.rpc({"op": "build_status"}), {"ready": True}
            )
        self.assertEqual(len(run.call_args_list), 2)
        command = run.call_args_list[-1].args[0]
        self.assertIn("ProxyCommand=false", command)
        self.assertNotIn("-M", command)
        self.assertEqual(
            json.loads(run.call_args_list[-1].kwargs["input"]), {"op": "build_status"}
        )

    def test_retry_only_master_authentication_with_backoff(self):
        sequence = [
            result(255),
            result(255, error="Exceeded MaxStartups"),
            result(
                255, error="kex_exchange_identification: read: Connection reset by peer"
            ),
            result(),
            result(),
            result(out='{"ready":true}'),
        ]
        with (
            patch("livelife.ssh_transport.subprocess.run", side_effect=sequence) as run,
            patch("livelife.ssh_transport.time.sleep") as sleep,
            patch("livelife.ssh_transport.random.uniform", return_value=0),
        ):
            self.transport.rpc({"op": "ensure"})
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2])
        starts = [c for c in run.call_args_list if "-M" in c.args[0]]
        self.assertEqual(len(starts), 3)
        self.assertTrue(
            all("-N" in c.args[0] and "input" not in c.kwargs for c in starts)
        )
        self.assertEqual(sum("input" in c.kwargs for c in run.call_args_list), 1)

    def test_authentication_and_host_key_failures_are_not_retried(self):
        for error in (
            "Permission denied (publickey)",
            "Host key verification failed",
            "REMOTE HOST IDENTIFICATION HAS CHANGED",
        ):
            with (
                self.subTest(error=error),
                patch(
                    "livelife.ssh_transport.subprocess.run",
                    side_effect=[result(255), result(255, error=error)],
                ) as run,
                patch("livelife.ssh_transport.time.sleep") as sleep,
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "master establishment failed"
                ):
                    self.transport.rpc({"op": "ensure"})
                self.assertEqual(run.call_count, 2)
                sleep.assert_not_called()

    def test_response_loss_never_replays_mutation(self):
        with patch(
            "livelife.ssh_transport.subprocess.run",
            side_effect=[
                result(),
                result(
                    255, error="mux_client_request_session: read from master failed"
                ),
            ],
        ) as run:
            with self.assertRaisesRegex(RuntimeError, "operation not replayed"):
                self.transport.rpc({"op": "ensure"})
        self.assertEqual(sum("input" in c.kwargs for c in run.call_args_list), 1)

    def test_handshake_retry_is_bounded_and_sends_no_rpc(self):
        with (
            patch(
                "livelife.ssh_transport.subprocess.run",
                side_effect=[result(255)]
                + [result(255, error="Exceeded MaxStartups")] * 4,
            ) as run,
            patch("livelife.ssh_transport.time.sleep"),
        ):
            with self.assertRaises(RuntimeError):
                self.transport.rpc({"op": "ensure"})
        self.assertEqual(run.call_count, 5)
        self.assertFalse(any("input" in c.kwargs for c in run.call_args_list))

    def test_concurrent_process_style_callers_start_one_master_and_parallel_sessions(
        self,
    ):
        state = {"alive": False, "starts": 0}
        barrier = threading.Barrier(3)

        def execute(command, **kwargs):
            if "-O" in command:
                return result(0 if state["alive"] else 255)
            if "-M" in command:
                state["starts"] += 1
                time.sleep(0.03)
                state["alive"] = True
                return result()
            barrier.wait(timeout=3)
            return result(out='{"ready":true}')

        with patch("livelife.ssh_transport.subprocess.run", side_effect=execute):
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = [
                    pool.submit(
                        CourseSSH(self.root, self.command, "group5@example.test").rpc,
                        {"op": "build_status"},
                    )
                    for _ in range(3)
                ]
                self.assertEqual([f.result() for f in futures], [{"ready": True}] * 3)
        self.assertEqual(state["starts"], 1)

    def test_dead_socket_recovered_but_foreign_file_preserved(self):
        with socket.socket(socket.AF_UNIX) as sock:
            sock.bind(str(self.transport.socket))
        with patch(
            "livelife.ssh_transport.subprocess.run",
            side_effect=[result(255), result(), result(), result(out="{}")],
        ):
            self.transport.rpc({"op": "build_status"})
        self.assertFalse(self.transport.socket.exists())
        self.transport.socket.write_text("unexpected file")
        with patch("livelife.ssh_transport.subprocess.run", return_value=result(255)):
            with self.assertRaisesRegex(ValueError, "unexpected"):
                self.transport.rpc({"op": "build_status"})
        self.assertEqual(self.transport.socket.read_text(), "unexpected file")

    def test_private_socket_directory_and_lock_are_required(self):
        directory = self.root / "ssh"
        directory.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "private"):
            CourseSSH(self.root, self.command, "group5@example.test")
        directory.chmod(0o700)
        self.transport.lock.symlink_to(self.root / "outside")
        with self.assertRaises(OSError):
            self.transport.rpc({"op": "ensure"})
        self.assertFalse((self.root / "outside").exists())
        self.transport.lock.unlink()
        directory.rmdir()
        directory.symlink_to(self.root)
        with self.assertRaisesRegex(ValueError, "private"):
            CourseSSH(self.root, self.command, "group5@example.test")

    def test_rotated_credentials_do_not_reuse_old_master(self):
        candidate = self.root / "next-hosts"
        candidate.write_text("rotated test host")
        os.replace(candidate, self.hosts)
        next_transport = CourseSSH(self.root, self.command, "group5@example.test")
        self.assertNotEqual(self.transport.socket, next_transport.socket)


if __name__ == "__main__":
    unittest.main()
