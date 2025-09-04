import asyncio
import json
import websockets
import global_consts
import random
from typing import Any
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

PLAYER_LIST_BROADCAST_INTERVAL_SECONDS = 10
TIMER_BROADCAST_INTERVAL_SECONDS = 10
EMERGENCY_MEETING_LENGTH = 20
STARTING_TASK_COUNT = 5
GAME_TOTAL_LENGTH = 60 * 10
IMPOSTOR_AMOUNT = 0.3
MEETING_COOLDOWN = 45
DEBUG_LOGGING = True

consts = global_consts.Constants()

class Game: # type: ignore
    pass

class Player():
    def __init__(self, id: str, connection: websockets.ServerConnection, game: Game):
        self.id = id
        self.connection = connection
        self.is_alive = True
        self.is_impostor = False

        player_count = len(game.player_list)
        impostor_count = game.get_imposters_left()

        if (player_count <= 3) or ((impostor_count / player_count) <= IMPOSTOR_AMOUNT): # clamps impostor count to be always less than 30%
            self.is_impostor = random.random() <= IMPOSTOR_AMOUNT
        self.tasks_left = STARTING_TASK_COUNT if not self.is_impostor else 0
        self.game = game

    async def send_packet(self, raw_data: dict[str, Any], is_broadcast: bool):
        data_str = json.dumps(raw_data)
        try:
            if DEBUG_LOGGING and not is_broadcast:
                print(f"[SEND] To client {self.id}: {data_str}")
            await self.connection.send(data_str)
        except:
            print(f"Could not send packet {data_str} to client {self.id}")

    async def send_role(self):
        await self.send_packet({
            "type": consts.S2C_ASSIGN_PLAYER,
            "role": "impostor" if self.is_impostor else "crewmate",
            "id": self.id,
            "numberOfTasksLeft": self.tasks_left,
        }, False)

    async def kill(self):
        self.is_alive = False
        await self.send_packet({
            "type": consts.S2C_DEATH
        }, False)
        await self.game.update_counts()


class EmergencyMeeting():
    def __init__(self, player_list: dict[str, Player]):
        self.player_list = player_list
        self.votes: dict[str, int] = { player: 0 for player in player_list}

    async def end_after_timer(self):
        await asyncio.sleep(EMERGENCY_MEETING_LENGTH)
        player_max_voted = self.get_max_voted()
        if player_max_voted is not None:
            await player_max_voted.kill()

    def get_max_voted(self) -> Player | None:
        max_player = ""
        max_votes = -1
        for player in self.votes:
            if self.votes[player] == max_votes: # another player with the same number of votes found, cancel
                max_player = ""
            if self.votes[player] > max_votes:
                max_votes = self.votes[player]
                max_player = player

        if max_player in self.player_list:
            return self.player_list[max_player]
        return None

class Game():
    def __init__(self):
        self.player_list: dict[str, Player] = {}
        self.admin_list: list[websockets.ServerConnection] = []
        self.global_timer = GAME_TOTAL_LENGTH
        self.last_player_id = 1
        self.is_running = False
        self.emergency_meeting: None | EmergencyMeeting = None
        self.last_meeting_time = None

    def get_tasks_left(self):
        count = 0
        for player in self.player_list.values():
            if player.is_alive:
                count += player.tasks_left
        return count


    def get_crewmates_left(self):
        count = 0
        for player in self.player_list.values():
            if player.is_alive and not player.is_impostor:
                count += 1
        return count


    def get_imposters_left(self):
        count = 0
        for player in self.player_list.values():
            if player.is_alive and player.is_impostor:
                count += 1
        return count

    def get_meeting_cooldown_left(self):
        if self.last_meeting_time is None:
        # Game start case
            elapsed_since_start = GAME_TOTAL_LENGTH - self.global_timer
            remaining = MEETING_COOLDOWN - elapsed_since_start
            return max(0, remaining)
        else:
            remaining = MEETING_COOLDOWN - (asyncio.get_event_loop().time() - self.last_meeting_time)
            return max(0, remaining)

    async def run_timer_task(self):
        while self.global_timer > 0:
            await asyncio.sleep(1)
            if self.is_running and self.emergency_meeting == None:
                self.global_timer -= 1

        await self.unset_game_running("Crewmates Win") # time up


    async def broadcast_to_clients(self, message_raw: dict[Any, Any]):
        if DEBUG_LOGGING and len(self.player_list) > 0:
            print(f"[BROADCAST] To all clients: {message_raw}")
        client_ids = list(self.player_list.keys())
        tasks = [
            self.player_list[client_id].send_packet(message_raw, True)
            for client_id in client_ids
            if client_id in self.player_list
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


    async def broadcast_to_admins(self, message_raw: dict[Any, Any]):
        message = json.dumps(message_raw)
        tasks = [
            connection.send(message)
            for connection in self.admin_list
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def update_counts(self):
        await self.broadcast_to_clients({
            "type": consts.S2C_UPDATE_CREWMATE_COUNT,
            "count": self.get_crewmates_left()
        })
        await self.broadcast_to_clients({
            "type": consts.S2C_UPDATE_IMPOSTER_COUNT,
            "count": self.get_imposters_left()
        })
        await self.broadcast_to_clients({
            "type": consts.S2C_UPDATE_TASKS_COUNT,
            "count": self.get_tasks_left()
        })
        await self.broadcast_to_admins({
            "type": consts.S2A_SEND_PLAYER_LIST,
            "count": self.get_imposters_left()
        })


    async def broadcast_timer_task(self):
        while True:
            await asyncio.sleep(TIMER_BROADCAST_INTERVAL_SECONDS)
            await self.broadcast_to_clients({
                "type": consts.S2C_UPDATE_TIMER,
                "timer": self.global_timer
            })
            cooldown_left = self.get_meeting_cooldown_left()
            await self.broadcast_to_clients({
            "type": consts.S2C_MEETING_COOLDOWN,
            "secondsLeft": cooldown_left
                })
            await self.broadcast_to_clients({
                        "type": consts.S2C_UPDATE_TASKS_COUNT,
                        "count": self.get_tasks_left()
                    })

    async def set_game_running(self):
        self.is_running = True
        self.global_timer = GAME_TOTAL_LENGTH
        await self.broadcast_to_clients({
            "type": consts.S2C_GAME_STARTED
        })
        await self.update_counts()

    async def unset_game_running(self, reason: str):
        self.is_running = False
        self.global_timer = GAME_TOTAL_LENGTH
        await self.broadcast_to_clients({
            "type": consts.S2C_GAME_OVER,
            "reason": reason
        })

    async def end_meeting_after_timer(self):
        if self.emergency_meeting is None:
            raise Exception

        await self.emergency_meeting.end_after_timer()
        total_crewmates_left = self.get_crewmates_left()
        total_impostors_left = self.get_imposters_left()
        if total_crewmates_left <= total_impostors_left:
            await self.unset_game_running("Impostors Win")
            return
        if total_impostors_left <= 0:
            await self.unset_game_running("Crewmates Win")
            return

        player_votes_list: list[dict[str, Any]] = [
            {"id": player_id, "votes": votes}
            for player_id, votes in self.emergency_meeting.votes.items()
        ]

        highest_voted_id = None
        if player_votes_list:
            sorted_votes = sorted(player_votes_list, key=lambda x: x["votes"], reverse=True)
            top_votes = sorted_votes[0]["votes"]
    # Only keep one if it's unique
            top_candidates = [p["id"] for p in sorted_votes if p["votes"] == top_votes]
            if len(top_candidates) == 1:
                highest_voted_id = top_candidates[0]

        self.emergency_meeting = None

        await self.broadcast_to_clients({
            "type": consts.S2C_EMERGENCY_MEETING_END,
            "playerVotes": player_votes_list,
            "highestVotedID": highest_voted_id
        })

        self.last_meeting_time = asyncio.get_event_loop().time()

    async def process_client_message(self, msg: Any, player: Player):
        if DEBUG_LOGGING:
            print(f"[RECEIVE] From client {player.id}: {json.dumps(msg)}")
        match msg["type"]:
            case consts.C2S_TASK_DONE:
                if not player.is_alive:
                    return
                if player.tasks_left > 0:
                    player.tasks_left -= 1
                    total_tasks_left = self.get_tasks_left()

                    await self.broadcast_to_clients({
                        "type": consts.S2C_UPDATE_TASKS_COUNT,
                        "count": total_tasks_left
                    })

                    if total_tasks_left == 0:
                        await self.unset_game_running("Crewmates Win")

            case consts.C2S_IMPOSTER_KILL:
                # make sure killed player is valid
                killed_player = msg["playerID"]
                if killed_player == player.id:
                    return
                if killed_player not in self.player_list:
                    return
                killed_player = self.player_list[killed_player]
                if not player.is_impostor:
                    return
                if not player.is_alive:
                    return

                if killed_player.is_alive and not killed_player.is_impostor:
                    await killed_player.kill()
                    # update stuffffff
                    total_crewmates_left = self.get_crewmates_left()
                    total_impostors_left = self.get_imposters_left()

                    if total_crewmates_left <= total_impostors_left:
                        await self.unset_game_running("Impostors Win")
                    if total_impostors_left <= 0:
                        await self.unset_game_running("Crewmates Win")

            case consts.C2S_CALL_MEETING:
                if not player.is_alive:
                    return
                now = asyncio.get_event_loop().time()
                cooldown_left = self.get_meeting_cooldown_left()
                if cooldown_left > 0:
                    await player.send_packet({
                        "type": consts.S2C_MEETING_COOLDOWN,
                        "secondsLeft": cooldown_left
                    }, False)
                    return

                self.emergency_meeting = EmergencyMeeting(self.player_list)
                self.last_meeting_time = now
                await self.broadcast_to_clients({
                    "type": consts.S2C_EMERGENCY_MEETING
                })
                asyncio.create_task(self.end_meeting_after_timer())
                #added timer cooldown

            case consts.C2S_VOTE_MEETING:
                if not player.is_alive:
                    return
                if self.emergency_meeting != None:
                    if msg["playerID"] in self.emergency_meeting.votes:
                        self.emergency_meeting.votes[msg["playerID"]] += 1

            case _:
                print("invalid message:", msg, "from client", player.id)


    async def game_connection_handler(self, websocket: websockets.ServerConnection):
        client_id = str(self.last_player_id)
        player = Player(id=client_id, connection=websocket, game=self)
        await player.send_role()
        self.last_player_id += 1

        self.player_list[client_id] = player
        print(f"New client connected: {client_id}")

        try:
            while True:
                try:
                    msg = json.loads(await websocket.recv())
                except (ConnectionClosedOK, ConnectionClosedError):
                    break

                await self.process_client_message(msg, player)
        finally:
            del self.player_list[client_id]
            print(f"Client disconnected: {client_id}")


    async def broadcast_player_list_task(self):
        while True:
            await asyncio.sleep(PLAYER_LIST_BROADCAST_INTERVAL_SECONDS)

            players: list[dict[str, Any]] = [{
                "id": player.id,
                "isImposter": player.is_impostor,
                "isAlive": player.is_alive,
                "tasksLeft": player.tasks_left
            } for player in self.player_list.values()]

            await self.broadcast_to_admins({
                "type": consts.S2A_SEND_PLAYER_LIST,
                "players": players
            })

    async def process_admin_message(self, msg: Any):
        match msg["type"]:
            case consts.A2S_FORCE_START_GAME:
                await self.set_game_running()
            case consts.A2S_FORCE_STOP_GAME:
                await self.unset_game_running("Force Stopped")
            case consts.A2S_RESET_GAME:
                self.player_list = {}
                self.global_timer = GAME_TOTAL_LENGTH
                self.last_player_id = 1
                self.is_running = False
                self.emergency_meeting = None
                self.last_meeting_time = None
            case _:
                print("invalid message:", msg, "from admin")

    async def admin_connection_handler(self, websocket: websockets.ServerConnection):
        print(f"New admin connected")

        try:
            while True:
                try:
                    msg = json.loads(await websocket.recv())
                except (ConnectionClosedOK, ConnectionClosedError):
                    break
                await self.process_admin_message(msg)
        finally:
            print(f"Admin disconnected")

    async def run_game(self):
        async with websockets.serve(self.game_connection_handler, "0.0.0.0", 8765):
            print("Websocket server started on ws://0.0.0.0:8765")
            await asyncio.gather(
                self.run_timer_task(),
                self.broadcast_timer_task()
            )

    async def run_admin(self):
        async with websockets.serve(self.admin_connection_handler, "0.0.0.0", 54813):
            print("Admin server started on ws://0.0.0.0:54813")
            await self.broadcast_player_list_task()

    async def start_stuff(self):
        await asyncio.gather(
            self.run_game(),
            self.run_admin()
        )


if __name__ == "__main__":
    try:
        asyncio.run(Game().start_stuff())
    except KeyboardInterrupt:
        print("Server shutting down.")
