import asyncio
import os
import sys
import json

sys.path.insert(0, "./libs")
import websockets.exceptions
from websockets.asyncio.server import serve

PORT = int(os.environ.get("PORT", 3000))
PASSWORD = "z17dLew368OTY6"

curValidIDNumber: int = 1
def getCurValidID() -> str:
    global curValidIDNumber;
    resultID = "QTGOPYID" + str(curValidIDNumber).zfill(5)
    curValidIDNumber += 1;
    return resultID;

# ==================================================
# ==================================================

connectedClients: dict[str, asyncio.Queue] = {}
activeGames: dict[str, str] = {}

async def sendLoop(websocket, queue):
    while True:
        try:
            sendToClientMsg = await queue.get()
            await websocket.send(sendToClientMsg)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as errorMsg:
            print(f"[sendLoop Error]: {errorMsg}")


async def handler(websocket):
    clientID = None
    sendQueue = asyncio.Queue()
    sendTask = asyncio.create_task(sendLoop(websocket, sendQueue))

    try:
        while True:
            message = await websocket.recv()
            print(f"[Received message]: {message}")

            try:
                data: dict = json.loads(message);
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "tppe": "error",
                    "errorMsg": "Invalid JSON"
                }))
                continue

            if data.get("type") == "auth":
                if clientID in connectedClients:
                    await websocket.send(json.dumps({"error": "ClientID already connected"}))
                    return
                if data.get("password") == PASSWORD:
                    clientID = getCurValidID();
                    connectedClients[clientID] = sendQueue
                    await websocket.send(json.dumps({
                        "type": "confirmAuth",
                        "isAuthSuccessful": True,
                        "uniqueID": clientID
                    }))
                    print(f"[Auth success]: ClientID = {clientID}")
                else:
                    await websocket.send(json.dumps({
                        "type": "confirmAuth",
                        "isAuthSuccessful": False,
                    }))
                    print(f"[Auth failed]")

            elif data.get("type") == "goGameRequest":
                targetID = data.get("targetID")
                if (targetID == clientID):
                    await sendQueue.put(json.dumps({
                        "type": "itsYourID",
                        "info": f"ID = {targetID} is your ID"
                    }))
                    continue;
                if targetID in connectedClients:
                    targetQueue = connectedClients[targetID]

                    await targetQueue.put(json.dumps({
                        "type": "requestGoGame",
                        "requestID": clientID
                    }))
                    print(f"[Game request]: {clientID} wants to play with {targetID}")

                    await sendQueue.put(json.dumps({
                        "type": "log",
                        "info": "request was sent"
                    }))
                else:
                    await sendQueue.put(json.dumps({
                        "type": "targetIDNotFound",
                        "info": f"ID = {targetID} not found or not connected"
                    }))

            elif data.get("type") == "replyGoGameRequest":
                targetID = data.get("targetID")
                if targetID in connectedClients:
                    targetQueue = connectedClients[targetID]

                    if (data.get("reply") == True):
                        await targetQueue.put(json.dumps({
                            "type": "goGameRequestResult",
                            "result": True,
                            "userColor": data.get("opponentColor"),
                            "opponentColor": data.get("userColor")
                        }))

                        await sendQueue.put(json.dumps({
                            "type": "log",
                            "info": "reject info was sent"
                        }))

                        # connect two players
                        activeGames[clientID] = targetID
                        activeGames[targetID] = clientID

                    elif (data.get("reply") == False):
                        await targetQueue.put(json.dumps({
                            "type": "goGameRequestResult",
                            "result": False
                        }))

                        await sendQueue.put(json.dumps({
                            "type": "log",
                            "info": "reject info was sent"
                        }))
                    else:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "errorMsg": "Invalid JSON Content"
                        }))
                else:
                    await sendQueue.put(json.dumps({
                        "type": "targetIDNotFound",
                        "info": f"ID = {targetID} not found or not connected"
                    }))
            
            elif data.get("type") == "gameMove":
                if clientID not in activeGames:
                    await sendQueue.put(json.dumps({
                        "type": "error",
                        "errorMsg": "You're not in a game"
                    }))
                    continue

                opponentID = activeGames[clientID]
                if opponentID in connectedClients:
                    await connectedClients[opponentID].put(json.dumps({
                        "type": "gameMove",
                        "moveX": data.get("moveX"),
                        "moveY": data.get("moveY"),
                        "pass": data.get("pass"),
                        "resign": data.get("resign")
                    }))
                    print(f"[ID = {clientID} send to ID = {opponentID}]: {data}")
                else:
                    await sendQueue.put(json.dumps({
                        "type": "opponentDisconnected"
                    }))

            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "errorMsg": "Invalid JSON Content"
                }))

    except websockets.exceptions.ConnectionClosed as errorMsg:
        print(f"[Disconnected]: ClientID = {clientID}, ErrorMessage = {errorMsg}")

    except Exception as errorMsg:
        print(f"[handler Error]: {errorMsg}")

    finally:
        if clientID in activeGames:
            opponentID = activeGames[clientID]
            if opponentID in connectedClients:
                await connectedClients[opponentID].put(json.dumps({
                    "type": "opponentDisconnected"
                }))
            del activeGames[opponentID]
            del activeGames[clientID]

        if (clientID != None) and (clientID in connectedClients):
            del connectedClients[clientID]

        sendTask.cancel()
        try:
            await sendTask
        except asyncio.CancelledError:
            pass

async def main():
    async with serve(handler, "localhost", PORT) as server:
        print(f"[Server]: Startup (Serving on port {PORT})")
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
