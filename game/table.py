from .utils import *

# 进入赌桌
# ws.send_binary(struct.pack('>iii4s', AUTO_ENTER_TABLE, 16, 0, 'C001'.encode()))

# LoginGameExtResp
# 139266


global table_lock
global user_encryptKey
global user_decryptKey
global broad_decryptKey


table_lock = Lock()

user_encryptKey = None
user_decryptKey = None
broad_decryptKey = None


def get_table_cmd_login(login_info, vid):
    data = struct.pack('4s30s3s16s', vid.encode(), login_info.pid_username.encode(), b'\x05\x00\x00', login_info.token)
    flags = CLIENT_LOGIN_GAME_EXT_TRIAL if login_info.is_guest else CLIENT_LOGIN_GAME_EXT
    return struct.pack(f'>iii{len(data)}s', flags, 12 + len(data), 0, data)


def cmd_login(ws, login_info, vid):
    # 发送登录数据
    ws.send_binary(get_table_cmd_login(login_info, vid))


def cmd_enter_table(ws, login_info, vid):
    # 进入赌桌
    data = struct.pack('4s', vid.encode())
    ws.send_binary(struct.pack(f'>iii{len(data)}s', AUTO_ENTER_TABLE, 12 + len(data), 0, data))


def cmd_exit_table(ws):
    ws.send_binary(struct.pack(f'>iii', GAME_TABLE_EXIT, 12, 0))


def cmd_get_game_status(ws):
    ws.send_binary(struct.pack(f'>iii', GET_GAME_CURRENT_STATUS, 12, 0))


def cmd_down_bet(ws, enc_key, gmcode, money, down_type):
    """
        桌号： GC0011941610Z
        1 庄
        2 闲
        3 和
    """
    ratio = 1
    seq = 10000
    
    data = struct.pack('>iii14sHII', GAME_BET_EXT, 36, seq, gmcode.encode(), down_type, int(money) * ratio, ratio)
    data = xor_encrypt(data, enc_key)
    ws.send_binary(data)


def connect_table(login_info, vid):
    ws = create_connection(f'ws://{login_info.port_conf.domain}:{login_info.port_conf.game[vid]["port"]}')
    if ws.connected:
        test_data = bytes([0x00, 0x86, 0x00, 0x02, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00, 0x00])
        ws.send_binary(test_data)
        if ws.recv() == test_data:
            return ws
    return None

global buy_money
global fail_count

buy_money = 20
fail_count = 0
buy_type = 1


def process_table(login_info, ws, ws_data, vid):
    global user_encryptKey
    global user_decryptKey
    global broad_decryptKey
    global buy_money
    global fail_count
    global buy_type

    (flags, ) = struct.unpack('>i', ws_data[:4])
    # output_text('table ' + str(flags))

    # LoginGameExtResp
    if flags == 139266:
        flags, length, _, retCode, vid, deviceType, reserve1, reserve2 = struct.unpack('>iiiI4sBBB', ws_data[:23])
        vid = trim(vid).decode()

        if retCode == 0:
            output_text('table 登录成功')

            # 重置加密key
            # user_encryptKey = None
            cmd_exit_table(ws)
            cmd_enter_table(ws, login_info, vid)
            
        else:
            ws.close()
            output_text('table 登录失败')
            return
    
    # AutoEnterTableVidResp
    elif flags == 73735:
        flags, length, _, retCode, vid, table_code, seat = struct.unpack('>iiii4s4sB', ws_data[:25])
        vid = trim(vid).decode()
        table_code = trim(table_code).decode()
        if retCode == 0:
            output_text('table 进入成功')

            cmd_get_game_status(ws)
            # 开始心跳
            start_hear(ws)            
        else:
            output_text('table 进入失败')

    # GameNoBetWarnResp
    elif flags == 131103:
        flags, length, _, roundNum = struct.unpack('>iiiB', ws_data[:13])
        cmd_exit_table(ws)
        cmd_enter_table(ws, login_info, vid)
        output_text(f'table 未下注警告: {roundNum} -----------------------------')
        
    # onPayoutOtherResp
    elif flags == 131129:
        output_table_text('onPayoutOtherResp')
    
    # VideoRealtimeInfoExtResp
    elif flags == 196663:
        output_table_text('VideoRealtimeInfoExtResp')
    # VideoRealtimeInfoResp  用户下注信息
    elif flags == 131127:
        output_table_text('VideoRealtimeInfoResp')
    # UpdateBalanceResp
    elif flags == 131106:
        flags, length, _, val, seq = struct.unpack('>iiidi', ws_data[:24])
        output_table_text('UpdateBalanceResp')
    # GameStartResp
    elif flags == 131083:
        flags, length, result, gmcode, span = struct.unpack('>iii14sH', ws_data[:28])
        gmcode = trim(gmcode).decode()
        ws.send_binary(struct.pack('>iii', 1, 12, result))
        
        """
        buy_type = 2
        buy_money = 20
        # 连续3次以上长龙庄就不买
        if fail_count <= 2:
            cmd_down_bet(ws, user_encryptKey, gmcode, buy_money, buy_type)    
        
            print('----GameStartResp----')
            print('桌号: ' + gmcode)
            print('下注: ' + str(int(buy_money)))
            print('购买: ' + ['庄', '闲', '和'][buy_type - 1])
        else:
            buy_money = 20
            fail_count = 0
        """
    elif flags == 172049:
        print(1)
        
    # GamePayoutMeResp
    elif flags == 131088:
        flags, length, _, gmcode, payout, balance, ptNum = struct.unpack('>iii14sddB', ws_data[:43])
        gmcode = trim(gmcode).decode()
        
    
        print('----GamePayoutMeResp----')
        print(f'balance: {balance}')
        print(f'payout: {payout}')
        print(f'ptNum: {ptNum}')
        
        if int(payout) > 0:
            buy_money = 20
            fail_count = 0
            
        elif int(payout) < 0:
            buy_money += buy_money
            fail_count += 1
             
    
   # GameBetResp
    elif flags == 131075:
        output_table_text('GameBetResp')
        flags, length, _, retCode = struct.unpack('>iiii', ws_data[:16])
        if retCode == 0:
            print('下注: 成功')
        else:
            print('下注: 失败')
            
        
    
    # GameTablePoolResp
    elif flags == 172083:
        output_table_text('GameTablePoolResp')
    # VideoStatusInfoResp
    elif flags == 131125:
        output_table_text('VideoStatusInfoResp')
    # DealerInfoResp
    elif flags == 131079:
        output_table_text('DealerInfoResp')
    # LedDealerInfoResp
    elif flags == 131077:
        output_table_text('LedDealerInfoResp')
   # UserPositionResp
    elif flags == 139290:
        output_table_text('UserPositionResp')
   # UserPositionResp
    elif flags == 131098:
        output_table_text('UserPositionResp')
   # UserPositionResp
    elif flags == 131092:
        output_table_text('UserPositionResp')
   # UserPositionResp
    elif flags == 131078:
        output_table_text('UserPositionResp')
   # PersonalLimitResp
    elif flags == 131119:
        output_table_text('PersonalLimitResp')
   # TableLimitResp
    elif flags == 131096:
        output_table_text('TableLimitResp')
   # GameTablePoolResp
    elif flags == 131123:
        output_table_text('GameTablePoolResp')
   # GameJettonResp
    elif flags == 131126:
        output_table_text('GameJettonResp')
   # GameJettonExtResp
    elif flags == 172086:
        output_table_text('GameJettonExtResp')
    # 密匙
    elif flags == 73986:
        # (user_encryptKey, ) = struct.unpack('>I', ws_data[49:53])
        pass

    elif flags == 301825:
        flags, length, seqNo, key_type,  key  = struct.unpack('>iiiBI', ws_data[:17])
        
        # userencryptKey
        if key_type == 0:
            if not user_encryptKey:
                user_encryptKey = key
            
            Y2R = random.randint(1, 1000)
            a = ctypes.c_uint(Y2R ^ user_encryptKey & 1688052650 | -2147483648).value | 0
            b = ctypes.c_uint(user_encryptKey ^ key | 0).value 
            # a = 0
            # b = user_encryptKey ^ key
            user_encryptKey = key

            ws.send_binary(struct.pack('>iiII', 301826, 16, a, b))

        # userDecryptKey
        # 这个用于解密
        elif key_type == 1: 
            user_decryptKey = key

    # broadcastDecryptKey
    elif flags == 301569:
        # 这个用于加密??
        flags, length, seqNo, broad_decryptKey  = struct.unpack('>iiIi', ws_data[:16])

    elif flags == 301854:
        pass
    
    elif flags == [133692, 135228]:
        flags, length, seqNo  = struct.unpack('>iiI', ws_data[:12])

    elif flags == 131130:
        # output_table_text(ws_data)
        pass

    # 心跳
    elif flags == 135195:
        test_data = bytes([0x00, 0x86, 0x00, 0x02, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00, 0x00])
        ws.send_binary(test_data)
    
    # GameCurrentStatusResp(没生效)
    elif flags == 131094:
        flags, length, _, vid, gmtype, status, gmcode  = struct.unpack('>iii4s4sB14s', ws_data[:35])
        vid = trim(vid).decode()
        # BAC
        gmtype = trim(gmtype).decode()
        # 桌号
        gmcode = trim(gmcode).decode()
        
        timeout, max_timeout = struct.unpack('>HH', ws_data[-4:])
    
    # 需要解密的内容
    elif flags == 301840:
        flags, length, _, ws_data  = struct.unpack('>iii{len(ws_data) - 12}s', ws_data)
        process_table(login_info, ws, ws_data, vid)
        
        
    # RestShoecodeResp
    elif flags == 131100:
        output_table_text('RestShoecodeResp')

    # DealCardListResp
    elif flags == 368642:
        output_table_text('DealCardListResp')
    # DealCardResp
    elif flags == 327682:
        output_table_text('DealCardResp')
    else:
        output_table_text('table: ' + str(flags))


def start_table(login_info, vid):
    global table_lock
    output_text('table 开始监控')
    try:
        ws = connect_table(login_info, vid)
        if ws.connected:
            # road
            # start_road(login_info)
            cmd_login(ws, login_info, vid)

        while ws.connected:
            ws_data = ws.recv()
            if len(ws_data) >= 12:
                with table_lock:
                    try:
                        process_table(login_info, ws, ws_data, vid)
                        
                    except:
                        import traceback
                        output_text(traceback.print_exc())
                        output_text('table 处理消息异常')
            else:
                output_text('table 数据异常')
    except:
        import traceback
        output_text(traceback.print_exc())
        output_text('table 异常结束')
    output_text('table 关闭处理')




# CRYPTO_USER_KEY_ACK