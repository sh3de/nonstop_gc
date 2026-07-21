import sys
import os

# 1. Сначала добавляем папку proto в путь поиска модулей
proto_path = os.path.join(os.path.dirname(__file__), 'proto')
if proto_path not in sys.path:
    sys.path.insert(0, proto_path)

# 2. Только ПОСЛЕ этого импортируем протобуфы
import gcsystemmsgs_pb2 as gc_sys
import cstrike15_gcmessages_pb2 as csgo_pb

# ID сообщений CS:GO GC
MSG_CLIENT_HELLO = 9109
MSG_GC_WELCOME = 9110
MSG_SO_CACHE_SUBSCRIBED = 1073


class CSGOGameCoordinator:
    def __init__(self):
        pass

    def build_welcome_packet(self) -> bytes:
        """Формирует пакет Welcome (убирает сообщение про обновление игры)."""
        welcome = csgo_pb.CMsgGCCStrike15_v2_MatchmakingGC2ClientWelcome()
        welcome.version = 13855         # Актуальная версия legacy CS:GO
        welcome.account_status = 1       # Status: Prime / Normal

        # При желании можно сразу задать звание
        welcome.ranking.account_id = 12345678
        welcome.ranking.rank_id = 18    # Global Elite
        welcome.ranking.wins = 500

        return welcome.SerializeToString()

    def build_inventory_packet(self, account_id: int = 12345678) -> bytes:
        """Формирует пакет SO Cache с Керамбитом."""
        cache = csgo_pb.CMsgSOCacheSubscribed()
        cache.owner.account_id = account_id

        # Создаем предмет: Керамбит
        item = csgo_pb.CSOEconItem()
        item.id = 1001
        item.account_id = account_id
        item.inventory = 1
        item.def_index = 507  # 507 = Karambit
        item.quantity = 1
        item.level = 1
        item.quality = 3      # ★ (Unusual / Knife)
        item.rarity = 6       # Covert (Красный)
        item.origin = 8       # Found in Crate

        # Добавляем объект в тип 1 (Type 1 = CSOEconItem)
        sub_type = cache.objects.add()
        sub_type.type_id = 1
        sub_type.object_data.append(item.SerializeToString())

        return cache.SerializeToString()

    def pack_gc_message(self, msg_type: int, payload: bytes) -> bytes:
        """
        Упаковывает protobuf-сообщение в заголовок GC.
        Заголовок CS:GO GC состоит из 32-битного ID сообщения и длины/флагов.
        """
        # Убираем флаг protobuf (0x80000000), если он есть
        raw_msg_type = msg_type & ~0x80000000
        
        # Заголовок: [4 байта: Type] + [4 байта: Length]
        header = struct.pack('<II', raw_msg_type, len(payload))
        return header + payload

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info('peername')
        print(f"[GC] Новое подключение: {peer}")

        try:
            while True:
                # Читаем заголовок пакета (8 байт)
                header = await reader.readexact(8)
                msg_type, length = struct.unpack('<II', header)
                
                # Читаем полезную нагрузку
                payload = await reader.readexact(length)
                print(f"[GC] Получен пакет ID: {msg_type}, размер: {length} байт")

                # Обработка ClientHello (когда игра запускается)
                if msg_type == MSG_CLIENT_HELLO:
                    print(" ➔ Клиент отправил ClientHello. Отправляем Welcome & Inventory...")

                    # 1. Отправляем Welcome
                    welcome_data = self.build_welcome_packet()
                    packet_welcome = self.pack_gc_message(MSG_GC_WELCOME, welcome_data)
                    writer.write(packet_welcome)

                    # 2. Отправляем Инвентарь
                    inventory_data = self.build_inventory_packet()
                    packet_inv = self.pack_gc_message(MSG_SO_CACHE_SUBSCRIBED, inventory_data)
                    writer.write(packet_inv)

                    await writer.drain()

        except asyncio.IncompleteReadError:
            print(f"[GC] Клиент {peer} отключился.")
        except Exception as e:
            print(f"[GC] Ошибка соединения {peer}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()


async def main():
    gc = CSGOGameCoordinator()
    
    # Запускаем сервер на порту 8080 (или process.env.PORT для Render)
    port = int(os.environ.get("PORT", 8080))
    server = await asyncio.start_server(gc.handle_client, '0.0.0.0', port)

    print(f"🚀 GC Server (Python) запущен на порту {port}...")
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
