# ============== Message Definitions ==============
# message type is always included in the body, for example:
# {
#   "type": S2C_DEATH
# }
# even though S2C_DEATH does not have any parameters

class Constants():
    def __init__(self):
        # ============== Server to Client ==============
        self.S2C_DEATH = "S2C_DEATH"
        # sent to a player on their death
        # body: { }

        self.S2C_UPDATE_TIMER = "S2C_UPDATE_TIMER"

        self.S2C_MEETING_COOLDOWN = "S2C_MEETING_COOLDOWN"
        # resyncs timer, broadcast to all every TIMER_BROADCAST_INTERVAL_SECONDS seconds
        # body: { "timer": <timer value> }

        self.S2C_UPDATE_IMPOSTER_COUNT = "S2C_UPDATE_IMPOSTER_COUNT"
        # updates imposter count, broadcast to all
        # body: { "count": <count> }

        self.S2C_UPDATE_CREWMATE_COUNT = "S2C_UPDATE_CREWMATE_COUNT"
        # updates crewmate count, broadcast to all
        # body: { "count": <count> }

        self.S2C_UPDATE_TASKS_COUNT = "S2C_UPDATE_TASKS_COUNT"
        # updates task count, broadcast to all
        # body: { "count": <count> }

        self.S2C_EMERGENCY_MEETING = "S2C_EMERGENCY_MEETING"
        # announces an emergency meeting, broadcast to all
        # body: { }

        self.S2C_EMERGENCY_MEETING_END = "S2C_EMERGENCY_MEETING_END"
        # ends an emergency meeting, broadcast to all
        # body: { 
        #   "playerVotes": [ 
        #       { 
        #           "id": <player id>, 
        #           "votes": <number of votes for this player> 
        #       }, ... 
        #   ] 
        # }

        self.S2C_ASSIGN_PLAYER = "S2C_ASSIGN_PLAYER"
        # assigns a role, id, and initial values to each player
        # is also sent after reconnect
        # body: {
        #   "role": "imposter" | "crewmate",
        #   "id": <player id>,
        #   "numberOfTasksLeft": <count>,
        # }

        self.S2C_GAME_STARTED = "S2C_GAME_STARTED"
        # signals start of game, broadcast to all
        # body: { }

        self.S2C_GAME_OVER = "S2C_GAME_OVER"
        # signals end of game, broadcast to all
        # body: { "reason": "Force Stopped"|"Crewmates Win"|"Imposters Win" }

        # ============== Client to Server ==============

        self.C2S_TASK_DONE = "C2S_TASK_DONE"
        # sent to server when a task is done
        # body: { }

        self.C2S_VOTE_MEETING = "C2S_VOTE_MEETING"
        # sent to server when voting in an emergency meeting
        # body: { "playerID": <id of player to vote for> }

        self.C2S_IMPOSTER_KILL = "C2S_IMPOSTER_KILL"
        # sent to server when an imposter kills a crewmate
        # body: { "playerID": <id of player killed> }

        self.C2S_CALL_MEETING = "C2S_CALL_MEETING"
        # sent to server when someone calls a meeting
        # body: { }

        self.C2S_TRY_RECONNECT = "C2S_TRY_RECONNECT"
        # sent to server when trying to reconnect
        # body: { "playerID": <id of player who wants to reconnect> }

        # ============== Admin to Server ==============

        self.A2S_FORCE_START_GAME = "A2S_FORCE_START_GAME"
        # sent to server by an admin to force start the game
        # body: { }

        self.A2S_FORCE_STOP_GAME = "A2S_FORCE_STOP_GAME"
        # sent to server by an admin to force stop the game
        # body: { }

        self.A2S_RESET_GAME = "A2S_RESET_GAME"
        # sent to server by an admin to reset the game
        # body: { }

        # ============== Server to Admin ==============

        self.S2A_SEND_PLAYER_LIST = "S2A_SEND_PLAYER_LIST"
        # sends player list, broadcast to all admins every PLAYER_LIST_BROADCAST_INTERVAL_SECONDS seconds
        # body: {
        #   "players": [
        #     {
        #       "id": <player id>,
        #       "isImposter": boolean,
        #       "isAlive": boolean,
        #     },
        #     ...
        #   ] 
        # }
