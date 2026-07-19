fn text_byte_at(id: tryte, index: tryte) -> tryte:
    match id <=> 1:
        0:
            match index <=> 0:
                0:
                    return 46
                -1:
                    skip_1_0: tryte = 0
                1:
                    skip_1_0: tryte = 0
            match index <=> 1:
                0:
                    return 115
                -1:
                    skip_1_1: tryte = 0
                1:
                    skip_1_1: tryte = 0
            match index <=> 2:
                0:
                    return 51
                -1:
                    skip_1_2: tryte = 0
                1:
                    skip_1_2: tryte = 0
            match index <=> 3:
                0:
                    return 97
                -1:
                    skip_1_3: tryte = 0
                1:
                    skip_1_3: tryte = 0
            match index <=> 4:
                0:
                    return 115
                -1:
                    skip_1_4: tryte = 0
                1:
                    skip_1_4: tryte = 0
            match index <=> 5:
                0:
                    return 109
                -1:
                    skip_1_5: tryte = 0
                1:
                    skip_1_5: tryte = 0
            return 0
        -1:
            skip_id_1: tryte = 0
        1:
            skip_id_1: tryte = 0
    match id <=> 2:
        0:
            match index <=> 0:
                0:
                    return 46
                -1:
                    skip_2_0: tryte = 0
                1:
                    skip_2_0: tryte = 0
            match index <=> 1:
                0:
                    return 102
                -1:
                    skip_2_1: tryte = 0
                1:
                    skip_2_1: tryte = 0
            match index <=> 2:
                0:
                    return 117
                -1:
                    skip_2_2: tryte = 0
                1:
                    skip_2_2: tryte = 0
            match index <=> 3:
                0:
                    return 110
                -1:
                    skip_2_3: tryte = 0
                1:
                    skip_2_3: tryte = 0
            match index <=> 4:
                0:
                    return 99
                -1:
                    skip_2_4: tryte = 0
                1:
                    skip_2_4: tryte = 0
            match index <=> 5:
                0:
                    return 116
                -1:
                    skip_2_5: tryte = 0
                1:
                    skip_2_5: tryte = 0
            match index <=> 6:
                0:
                    return 105
                -1:
                    skip_2_6: tryte = 0
                1:
                    skip_2_6: tryte = 0
            match index <=> 7:
                0:
                    return 111
                -1:
                    skip_2_7: tryte = 0
                1:
                    skip_2_7: tryte = 0
            match index <=> 8:
                0:
                    return 110
                -1:
                    skip_2_8: tryte = 0
                1:
                    skip_2_8: tryte = 0
            return 0
        -1:
            skip_id_2: tryte = 0
        1:
            skip_id_2: tryte = 0
    match id <=> 3:
        0:
            match index <=> 0:
                0:
                    return 46
                -1:
                    skip_3_0: tryte = 0
                1:
                    skip_3_0: tryte = 0
            match index <=> 1:
                0:
                    return 114
                -1:
                    skip_3_1: tryte = 0
                1:
                    skip_3_1: tryte = 0
            match index <=> 2:
                0:
                    return 101
                -1:
                    skip_3_2: tryte = 0
                1:
                    skip_3_2: tryte = 0
            match index <=> 3:
                0:
                    return 103
                -1:
                    skip_3_3: tryte = 0
                1:
                    skip_3_3: tryte = 0
            match index <=> 4:
                0:
                    return 105
                -1:
                    skip_3_4: tryte = 0
                1:
                    skip_3_4: tryte = 0
            match index <=> 5:
                0:
                    return 115
                -1:
                    skip_3_5: tryte = 0
                1:
                    skip_3_5: tryte = 0
            match index <=> 6:
                0:
                    return 116
                -1:
                    skip_3_6: tryte = 0
                1:
                    skip_3_6: tryte = 0
            match index <=> 7:
                0:
                    return 101
                -1:
                    skip_3_7: tryte = 0
                1:
                    skip_3_7: tryte = 0
            match index <=> 8:
                0:
                    return 114
                -1:
                    skip_3_8: tryte = 0
                1:
                    skip_3_8: tryte = 0
            return 0
        -1:
            skip_id_3: tryte = 0
        1:
            skip_id_3: tryte = 0
    match id <=> 4:
        0:
            match index <=> 0:
                0:
                    return 46
                -1:
                    skip_4_0: tryte = 0
                1:
                    skip_4_0: tryte = 0
            match index <=> 1:
                0:
                    return 108
                -1:
                    skip_4_1: tryte = 0
                1:
                    skip_4_1: tryte = 0
            match index <=> 2:
                0:
                    return 97
                -1:
                    skip_4_2: tryte = 0
                1:
                    skip_4_2: tryte = 0
            match index <=> 3:
                0:
                    return 98
                -1:
                    skip_4_3: tryte = 0
                1:
                    skip_4_3: tryte = 0
            match index <=> 4:
                0:
                    return 101
                -1:
                    skip_4_4: tryte = 0
                1:
                    skip_4_4: tryte = 0
            match index <=> 5:
                0:
                    return 108
                -1:
                    skip_4_5: tryte = 0
                1:
                    skip_4_5: tryte = 0
            return 0
        -1:
            skip_id_4: tryte = 0
        1:
            skip_id_4: tryte = 0
    match id <=> 5:
        0:
            match index <=> 0:
                0:
                    return 46
                -1:
                    skip_5_0: tryte = 0
                1:
                    skip_5_0: tryte = 0
            match index <=> 1:
                0:
                    return 101
                -1:
                    skip_5_1: tryte = 0
                1:
                    skip_5_1: tryte = 0
            match index <=> 2:
                0:
                    return 110
                -1:
                    skip_5_2: tryte = 0
                1:
                    skip_5_2: tryte = 0
            match index <=> 3:
                0:
                    return 100
                -1:
                    skip_5_3: tryte = 0
                1:
                    skip_5_3: tryte = 0
            return 0
        -1:
            skip_id_5: tryte = 0
        1:
            skip_id_5: tryte = 0
    match id <=> 6:
        0:
            match index <=> 0:
                0:
                    return 45
                -1:
                    skip_6_0: tryte = 0
                1:
                    skip_6_0: tryte = 0
            match index <=> 1:
                0:
                    return 62
                -1:
                    skip_6_1: tryte = 0
                1:
                    skip_6_1: tryte = 0
            return 0
        -1:
            skip_id_6: tryte = 0
        1:
            skip_id_6: tryte = 0
    match id <=> 7:
        0:
            match index <=> 0:
                0:
                    return 32
                -1:
                    skip_7_0: tryte = 0
                1:
                    skip_7_0: tryte = 0
            return 0
        -1:
            skip_id_7: tryte = 0
        1:
            skip_id_7: tryte = 0
    match id <=> 8:
        0:
            match index <=> 0:
                0:
                    return 44
                -1:
                    skip_8_0: tryte = 0
                1:
                    skip_8_0: tryte = 0
            return 0
        -1:
            skip_id_8: tryte = 0
        1:
            skip_id_8: tryte = 0
    match id <=> 9:
        0:
            match index <=> 0:
                0:
                    return 59
                -1:
                    skip_9_0: tryte = 0
                1:
                    skip_9_0: tryte = 0
            match index <=> 1:
                0:
                    return 32
                -1:
                    skip_9_1: tryte = 0
                1:
                    skip_9_1: tryte = 0
            match index <=> 2:
                0:
                    return 115
                -1:
                    skip_9_2: tryte = 0
                1:
                    skip_9_2: tryte = 0
            match index <=> 3:
                0:
                    return 111
                -1:
                    skip_9_3: tryte = 0
                1:
                    skip_9_3: tryte = 0
            match index <=> 4:
                0:
                    return 117
                -1:
                    skip_9_4: tryte = 0
                1:
                    skip_9_4: tryte = 0
            match index <=> 5:
                0:
                    return 114
                -1:
                    skip_9_5: tryte = 0
                1:
                    skip_9_5: tryte = 0
            match index <=> 6:
                0:
                    return 99
                -1:
                    skip_9_6: tryte = 0
                1:
                    skip_9_6: tryte = 0
            match index <=> 7:
                0:
                    return 101
                -1:
                    skip_9_7: tryte = 0
                1:
                    skip_9_7: tryte = 0
            match index <=> 8:
                0:
                    return 61
                -1:
                    skip_9_8: tryte = 0
                1:
                    skip_9_8: tryte = 0
            return 0
        -1:
            skip_id_9: tryte = 0
        1:
            skip_id_9: tryte = 0
    match id <=> 10:
        0:
            match index <=> 0:
                0:
                    return 10
                -1:
                    skip_10_0: tryte = 0
                1:
                    skip_10_0: tryte = 0
            return 0
        -1:
            skip_id_10: tryte = 0
        1:
            skip_id_10: tryte = 0
    match id <=> 11:
        0:
            match index <=> 0:
                0:
                    return 13
                -1:
                    skip_11_0: tryte = 0
                1:
                    skip_11_0: tryte = 0
            return 0
        -1:
            skip_id_11: tryte = 0
        1:
            skip_id_11: tryte = 0
    match id <=> 12:
        0:
            match index <=> 0:
                0:
                    return 116
                -1:
                    skip_12_0: tryte = 0
                1:
                    skip_12_0: tryte = 0
            match index <=> 1:
                0:
                    return 114
                -1:
                    skip_12_1: tryte = 0
                1:
                    skip_12_1: tryte = 0
            match index <=> 2:
                0:
                    return 121
                -1:
                    skip_12_2: tryte = 0
                1:
                    skip_12_2: tryte = 0
            match index <=> 3:
                0:
                    return 116
                -1:
                    skip_12_3: tryte = 0
                1:
                    skip_12_3: tryte = 0
            match index <=> 4:
                0:
                    return 101
                -1:
                    skip_12_4: tryte = 0
                1:
                    skip_12_4: tryte = 0
            return 0
        -1:
            skip_id_12: tryte = 0
        1:
            skip_id_12: tryte = 0
    match id <=> 100:
        0:
            match index <=> 0:
                0:
                    return 109
                -1:
                    skip_100_0: tryte = 0
                1:
                    skip_100_0: tryte = 0
            match index <=> 1:
                0:
                    return 97
                -1:
                    skip_100_1: tryte = 0
                1:
                    skip_100_1: tryte = 0
            match index <=> 2:
                0:
                    return 105
                -1:
                    skip_100_2: tryte = 0
                1:
                    skip_100_2: tryte = 0
            match index <=> 3:
                0:
                    return 110
                -1:
                    skip_100_3: tryte = 0
                1:
                    skip_100_3: tryte = 0
            return 0
        -1:
            skip_id_100: tryte = 0
        1:
            skip_id_100: tryte = 0
    match id <=> 101:
        0:
            match index <=> 0:
                0:
                    return 101
                -1:
                    skip_101_0: tryte = 0
                1:
                    skip_101_0: tryte = 0
            match index <=> 1:
                0:
                    return 110
                -1:
                    skip_101_1: tryte = 0
                1:
                    skip_101_1: tryte = 0
            match index <=> 2:
                0:
                    return 116
                -1:
                    skip_101_2: tryte = 0
                1:
                    skip_101_2: tryte = 0
            match index <=> 3:
                0:
                    return 114
                -1:
                    skip_101_3: tryte = 0
                1:
                    skip_101_3: tryte = 0
            match index <=> 4:
                0:
                    return 121
                -1:
                    skip_101_4: tryte = 0
                1:
                    skip_101_4: tryte = 0
            return 0
        -1:
            skip_id_101: tryte = 0
        1:
            skip_id_101: tryte = 0
    match id <=> 102:
        0:
            match index <=> 0:
                0:
                    return 48
                -1:
                    skip_102_0: tryte = 0
                1:
                    skip_102_0: tryte = 0
            match index <=> 1:
                0:
                    return 46
                -1:
                    skip_102_1: tryte = 0
                1:
                    skip_102_1: tryte = 0
            match index <=> 2:
                0:
                    return 53
                -1:
                    skip_102_2: tryte = 0
                1:
                    skip_102_2: tryte = 0
            match index <=> 3:
                0:
                    return 46
                -1:
                    skip_102_3: tryte = 0
                1:
                    skip_102_3: tryte = 0
            match index <=> 4:
                0:
                    return 48
                -1:
                    skip_102_4: tryte = 0
                1:
                    skip_102_4: tryte = 0
            return 0
        -1:
            skip_id_102: tryte = 0
        1:
            skip_id_102: tryte = 0
    match id <=> 200:
        0:
            match index <=> 0:
                0:
                    return 84
                -1:
                    skip_200_0: tryte = 0
                1:
                    skip_200_0: tryte = 0
            match index <=> 1:
                0:
                    return 67
                -1:
                    skip_200_1: tryte = 0
                1:
                    skip_200_1: tryte = 0
            match index <=> 2:
                0:
                    return 79
                -1:
                    skip_200_2: tryte = 0
                1:
                    skip_200_2: tryte = 0
            match index <=> 3:
                0:
                    return 78
                -1:
                    skip_200_3: tryte = 0
                1:
                    skip_200_3: tryte = 0
            match index <=> 4:
                0:
                    return 83
                -1:
                    skip_200_4: tryte = 0
                1:
                    skip_200_4: tryte = 0
            match index <=> 5:
                0:
                    return 84
                -1:
                    skip_200_5: tryte = 0
                1:
                    skip_200_5: tryte = 0
            return 0
        -1:
            skip_id_200: tryte = 0
        1:
            skip_id_200: tryte = 0
    match id <=> 201:
        0:
            match index <=> 0:
                0:
                    return 84
                -1:
                    skip_201_0: tryte = 0
                1:
                    skip_201_0: tryte = 0
            match index <=> 1:
                0:
                    return 77
                -1:
                    skip_201_1: tryte = 0
                1:
                    skip_201_1: tryte = 0
            match index <=> 2:
                0:
                    return 79
                -1:
                    skip_201_2: tryte = 0
                1:
                    skip_201_2: tryte = 0
            match index <=> 3:
                0:
                    return 86
                -1:
                    skip_201_3: tryte = 0
                1:
                    skip_201_3: tryte = 0
            return 0
        -1:
            skip_id_201: tryte = 0
        1:
            skip_id_201: tryte = 0
    match id <=> 202:
        0:
            match index <=> 0:
                0:
                    return 84
                -1:
                    skip_202_0: tryte = 0
                1:
                    skip_202_0: tryte = 0
            match index <=> 1:
                0:
                    return 73
                -1:
                    skip_202_1: tryte = 0
                1:
                    skip_202_1: tryte = 0
            match index <=> 2:
                0:
                    return 78
                -1:
                    skip_202_2: tryte = 0
                1:
                    skip_202_2: tryte = 0
            match index <=> 3:
                0:
                    return 86
                -1:
                    skip_202_3: tryte = 0
                1:
                    skip_202_3: tryte = 0
            return 0
        -1:
            skip_id_202: tryte = 0
        1:
            skip_id_202: tryte = 0
    match id <=> 203:
        0:
            match index <=> 0:
                0:
                    return 84
                -1:
                    skip_203_0: tryte = 0
                1:
                    skip_203_0: tryte = 0
            match index <=> 1:
                0:
                    return 65
                -1:
                    skip_203_1: tryte = 0
                1:
                    skip_203_1: tryte = 0
            match index <=> 2:
                0:
                    return 68
                -1:
                    skip_203_2: tryte = 0
                1:
                    skip_203_2: tryte = 0
            match index <=> 3:
                0:
                    return 68
                -1:
                    skip_203_3: tryte = 0
                1:
                    skip_203_3: tryte = 0
            return 0
        -1:
            skip_id_203: tryte = 0
        1:
            skip_id_203: tryte = 0
    match id <=> 204:
        0:
            match index <=> 0:
                0:
                    return 84
                -1:
                    skip_204_0: tryte = 0
                1:
                    skip_204_0: tryte = 0
            match index <=> 1:
                0:
                    return 82
                -1:
                    skip_204_1: tryte = 0
                1:
                    skip_204_1: tryte = 0
            match index <=> 2:
                0:
                    return 69
                -1:
                    skip_204_2: tryte = 0
                1:
                    skip_204_2: tryte = 0
            match index <=> 3:
                0:
                    return 84
                -1:
                    skip_204_3: tryte = 0
                1:
                    skip_204_3: tryte = 0
            return 0
        -1:
            skip_id_204: tryte = 0
        1:
            skip_id_204: tryte = 0
    match id <=> 300:
        0:
            match index <=> 0:
                0:
                    return 114
                -1:
                    skip_300_0: tryte = 0
                1:
                    skip_300_0: tryte = 0
            match index <=> 1:
                0:
                    return 48
                -1:
                    skip_300_1: tryte = 0
                1:
                    skip_300_1: tryte = 0
            return 0
        -1:
            skip_id_300: tryte = 0
        1:
            skip_id_300: tryte = 0
    match id <=> 301:
        0:
            match index <=> 0:
                0:
                    return 114
                -1:
                    skip_301_0: tryte = 0
                1:
                    skip_301_0: tryte = 0
            match index <=> 1:
                0:
                    return 49
                -1:
                    skip_301_1: tryte = 0
                1:
                    skip_301_1: tryte = 0
            return 0
        -1:
            skip_id_301: tryte = 0
        1:
            skip_id_301: tryte = 0
    match id <=> 302:
        0:
            match index <=> 0:
                0:
                    return 114
                -1:
                    skip_302_0: tryte = 0
                1:
                    skip_302_0: tryte = 0
            match index <=> 1:
                0:
                    return 50
                -1:
                    skip_302_1: tryte = 0
                1:
                    skip_302_1: tryte = 0
            return 0
        -1:
            skip_id_302: tryte = 0
        1:
            skip_id_302: tryte = 0
    match id <=> 303:
        0:
            match index <=> 0:
                0:
                    return 114
                -1:
                    skip_303_0: tryte = 0
                1:
                    skip_303_0: tryte = 0
            match index <=> 1:
                0:
                    return 51
                -1:
                    skip_303_1: tryte = 0
                1:
                    skip_303_1: tryte = 0
            return 0
        -1:
            skip_id_303: tryte = 0
        1:
            skip_id_303: tryte = 0
    match id <=> 304:
        0:
            match index <=> 0:
                0:
                    return 114
                -1:
                    skip_304_0: tryte = 0
                1:
                    skip_304_0: tryte = 0
            match index <=> 1:
                0:
                    return 52
                -1:
                    skip_304_1: tryte = 0
                1:
                    skip_304_1: tryte = 0
            return 0
        -1:
            skip_id_304: tryte = 0
        1:
            skip_id_304: tryte = 0
    match id <=> 305:
        0:
            match index <=> 0:
                0:
                    return 114
                -1:
                    skip_305_0: tryte = 0
                1:
                    skip_305_0: tryte = 0
            match index <=> 1:
                0:
                    return 53
                -1:
                    skip_305_1: tryte = 0
                1:
                    skip_305_1: tryte = 0
            return 0
        -1:
            skip_id_305: tryte = 0
        1:
            skip_id_305: tryte = 0
    match id <=> 240:
        0:
            match index <=> 0:
                0:
                    return 49
                -1:
                    skip_240_0: tryte = 0
                1:
                    skip_240_0: tryte = 0
            match index <=> 1:
                0:
                    return 48
                -1:
                    skip_240_1: tryte = 0
                1:
                    skip_240_1: tryte = 0
            return 0
        -1:
            skip_id_240: tryte = 0
        1:
            skip_id_240: tryte = 0
    match id <=> 241:
        0:
            match index <=> 0:
                0:
                    return 52
                -1:
                    skip_241_0: tryte = 0
                1:
                    skip_241_0: tryte = 0
            return 0
        -1:
            skip_id_241: tryte = 0
        1:
            skip_id_241: tryte = 0
    match id <=> 250:
        0:
            match index <=> 0:
                0:
                    return 50
                -1:
                    skip_250_0: tryte = 0
                1:
                    skip_250_0: tryte = 0
            match index <=> 1:
                0:
                    return 58
                -1:
                    skip_250_1: tryte = 0
                1:
                    skip_250_1: tryte = 0
            match index <=> 2:
                0:
                    return 49
                -1:
                    skip_250_2: tryte = 0
                1:
                    skip_250_2: tryte = 0
            match index <=> 3:
                0:
                    return 54
                -1:
                    skip_250_3: tryte = 0
                1:
                    skip_250_3: tryte = 0
            match index <=> 4:
                0:
                    return 58
                -1:
                    skip_250_4: tryte = 0
                1:
                    skip_250_4: tryte = 0
            match index <=> 5:
                0:
                    return 51
                -1:
                    skip_250_5: tryte = 0
                1:
                    skip_250_5: tryte = 0
            match index <=> 6:
                0:
                    return 53
                -1:
                    skip_250_6: tryte = 0
                1:
                    skip_250_6: tryte = 0
            return 0
        -1:
            skip_id_250: tryte = 0
        1:
            skip_id_250: tryte = 0
    match id <=> 251:
        0:
            match index <=> 0:
                0:
                    return 50
                -1:
                    skip_251_0: tryte = 0
                1:
                    skip_251_0: tryte = 0
            match index <=> 1:
                0:
                    return 58
                -1:
                    skip_251_1: tryte = 0
                1:
                    skip_251_1: tryte = 0
            match index <=> 2:
                0:
                    return 53
                -1:
                    skip_251_2: tryte = 0
                1:
                    skip_251_2: tryte = 0
            match index <=> 3:
                0:
                    return 58
                -1:
                    skip_251_3: tryte = 0
                1:
                    skip_251_3: tryte = 0
            match index <=> 4:
                0:
                    return 50
                -1:
                    skip_251_4: tryte = 0
                1:
                    skip_251_4: tryte = 0
            match index <=> 5:
                0:
                    return 52
                -1:
                    skip_251_5: tryte = 0
                1:
                    skip_251_5: tryte = 0
            return 0
        -1:
            skip_id_251: tryte = 0
        1:
            skip_id_251: tryte = 0
    match id <=> 252:
        0:
            match index <=> 0:
                0:
                    return 51
                -1:
                    skip_252_0: tryte = 0
                1:
                    skip_252_0: tryte = 0
            match index <=> 1:
                0:
                    return 58
                -1:
                    skip_252_1: tryte = 0
                1:
                    skip_252_1: tryte = 0
            match index <=> 2:
                0:
                    return 49
                -1:
                    skip_252_2: tryte = 0
                1:
                    skip_252_2: tryte = 0
            match index <=> 3:
                0:
                    return 54
                -1:
                    skip_252_3: tryte = 0
                1:
                    skip_252_3: tryte = 0
            match index <=> 4:
                0:
                    return 58
                -1:
                    skip_252_4: tryte = 0
                1:
                    skip_252_4: tryte = 0
            match index <=> 5:
                0:
                    return 53
                -1:
                    skip_252_5: tryte = 0
                1:
                    skip_252_5: tryte = 0
            match index <=> 6:
                0:
                    return 51
                -1:
                    skip_252_6: tryte = 0
                1:
                    skip_252_6: tryte = 0
            return 0
        -1:
            skip_id_252: tryte = 0
        1:
            skip_id_252: tryte = 0
    match id <=> 253:
        0:
            match index <=> 0:
                0:
                    return 51
                -1:
                    skip_253_0: tryte = 0
                1:
                    skip_253_0: tryte = 0
            match index <=> 1:
                0:
                    return 58
                -1:
                    skip_253_1: tryte = 0
                1:
                    skip_253_1: tryte = 0
            match index <=> 2:
                0:
                    return 53
                -1:
                    skip_253_2: tryte = 0
                1:
                    skip_253_2: tryte = 0
            match index <=> 3:
                0:
                    return 58
                -1:
                    skip_253_3: tryte = 0
                1:
                    skip_253_3: tryte = 0
            match index <=> 4:
                0:
                    return 52
                -1:
                    skip_253_4: tryte = 0
                1:
                    skip_253_4: tryte = 0
            match index <=> 5:
                0:
                    return 50
                -1:
                    skip_253_5: tryte = 0
                1:
                    skip_253_5: tryte = 0
            return 0
        -1:
            skip_id_253: tryte = 0
        1:
            skip_id_253: tryte = 0
    match id <=> 254:
        0:
            match index <=> 0:
                0:
                    return 52
                -1:
                    skip_254_0: tryte = 0
                1:
                    skip_254_0: tryte = 0
            match index <=> 1:
                0:
                    return 58
                -1:
                    skip_254_1: tryte = 0
                1:
                    skip_254_1: tryte = 0
            match index <=> 2:
                0:
                    return 49
                -1:
                    skip_254_2: tryte = 0
                1:
                    skip_254_2: tryte = 0
            match index <=> 3:
                0:
                    return 52
                -1:
                    skip_254_3: tryte = 0
                1:
                    skip_254_3: tryte = 0
            match index <=> 4:
                0:
                    return 58
                -1:
                    skip_254_4: tryte = 0
                1:
                    skip_254_4: tryte = 0
            match index <=> 5:
                0:
                    return 54
                -1:
                    skip_254_5: tryte = 0
                1:
                    skip_254_5: tryte = 0
            match index <=> 6:
                0:
                    return 56
                -1:
                    skip_254_6: tryte = 0
                1:
                    skip_254_6: tryte = 0
            return 0
        -1:
            skip_id_254: tryte = 0
        1:
            skip_id_254: tryte = 0
    match id <=> 255:
        0:
            match index <=> 0:
                0:
                    return 52
                -1:
                    skip_255_0: tryte = 0
                1:
                    skip_255_0: tryte = 0
            match index <=> 1:
                0:
                    return 58
                -1:
                    skip_255_1: tryte = 0
                1:
                    skip_255_1: tryte = 0
            match index <=> 2:
                0:
                    return 53
                -1:
                    skip_255_2: tryte = 0
                1:
                    skip_255_2: tryte = 0
            match index <=> 3:
                0:
                    return 58
                -1:
                    skip_255_3: tryte = 0
                1:
                    skip_255_3: tryte = 0
            match index <=> 4:
                0:
                    return 53
                -1:
                    skip_255_4: tryte = 0
                1:
                    skip_255_4: tryte = 0
            match index <=> 5:
                0:
                    return 57
                -1:
                    skip_255_5: tryte = 0
                1:
                    skip_255_5: tryte = 0
            return 0
        -1:
            skip_id_255: tryte = 0
        1:
            skip_id_255: tryte = 0
    return 0

fn text_length(id: tryte) -> tryte:
    match id <=> 1:
        0:
            return 6
        -1:
            skip_len_1: tryte = 0
        1:
            skip_len_1: tryte = 0
    match id <=> 2:
        0:
            return 9
        -1:
            skip_len_2: tryte = 0
        1:
            skip_len_2: tryte = 0
    match id <=> 3:
        0:
            return 9
        -1:
            skip_len_3: tryte = 0
        1:
            skip_len_3: tryte = 0
    match id <=> 4:
        0:
            return 6
        -1:
            skip_len_4: tryte = 0
        1:
            skip_len_4: tryte = 0
    match id <=> 5:
        0:
            return 4
        -1:
            skip_len_5: tryte = 0
        1:
            skip_len_5: tryte = 0
    match id <=> 6:
        0:
            return 2
        -1:
            skip_len_6: tryte = 0
        1:
            skip_len_6: tryte = 0
    match id <=> 7:
        0:
            return 1
        -1:
            skip_len_7: tryte = 0
        1:
            skip_len_7: tryte = 0
    match id <=> 8:
        0:
            return 1
        -1:
            skip_len_8: tryte = 0
        1:
            skip_len_8: tryte = 0
    match id <=> 9:
        0:
            return 9
        -1:
            skip_len_9: tryte = 0
        1:
            skip_len_9: tryte = 0
    match id <=> 10:
        0:
            return 1
        -1:
            skip_len_10: tryte = 0
        1:
            skip_len_10: tryte = 0
    match id <=> 11:
        0:
            return 1
        -1:
            skip_len_11: tryte = 0
        1:
            skip_len_11: tryte = 0
    match id <=> 12:
        0:
            return 5
        -1:
            skip_len_12: tryte = 0
        1:
            skip_len_12: tryte = 0
    match id <=> 100:
        0:
            return 4
        -1:
            skip_len_100: tryte = 0
        1:
            skip_len_100: tryte = 0
    match id <=> 101:
        0:
            return 5
        -1:
            skip_len_101: tryte = 0
        1:
            skip_len_101: tryte = 0
    match id <=> 102:
        0:
            return 5
        -1:
            skip_len_102: tryte = 0
        1:
            skip_len_102: tryte = 0
    match id <=> 200:
        0:
            return 6
        -1:
            skip_len_200: tryte = 0
        1:
            skip_len_200: tryte = 0
    match id <=> 201:
        0:
            return 4
        -1:
            skip_len_201: tryte = 0
        1:
            skip_len_201: tryte = 0
    match id <=> 202:
        0:
            return 4
        -1:
            skip_len_202: tryte = 0
        1:
            skip_len_202: tryte = 0
    match id <=> 203:
        0:
            return 4
        -1:
            skip_len_203: tryte = 0
        1:
            skip_len_203: tryte = 0
    match id <=> 204:
        0:
            return 4
        -1:
            skip_len_204: tryte = 0
        1:
            skip_len_204: tryte = 0
    match id <=> 300:
        0:
            return 2
        -1:
            skip_len_300: tryte = 0
        1:
            skip_len_300: tryte = 0
    match id <=> 301:
        0:
            return 2
        -1:
            skip_len_301: tryte = 0
        1:
            skip_len_301: tryte = 0
    match id <=> 302:
        0:
            return 2
        -1:
            skip_len_302: tryte = 0
        1:
            skip_len_302: tryte = 0
    match id <=> 303:
        0:
            return 2
        -1:
            skip_len_303: tryte = 0
        1:
            skip_len_303: tryte = 0
    match id <=> 304:
        0:
            return 2
        -1:
            skip_len_304: tryte = 0
        1:
            skip_len_304: tryte = 0
    match id <=> 305:
        0:
            return 2
        -1:
            skip_len_305: tryte = 0
        1:
            skip_len_305: tryte = 0
    match id <=> 240:
        0:
            return 2
        -1:
            skip_len_240: tryte = 0
        1:
            skip_len_240: tryte = 0
    match id <=> 241:
        0:
            return 1
        -1:
            skip_len_241: tryte = 0
        1:
            skip_len_241: tryte = 0
    match id <=> 250:
        0:
            return 7
        -1:
            skip_len_250: tryte = 0
        1:
            skip_len_250: tryte = 0
    match id <=> 251:
        0:
            return 6
        -1:
            skip_len_251: tryte = 0
        1:
            skip_len_251: tryte = 0
    match id <=> 252:
        0:
            return 7
        -1:
            skip_len_252: tryte = 0
        1:
            skip_len_252: tryte = 0
    match id <=> 253:
        0:
            return 6
        -1:
            skip_len_253: tryte = 0
        1:
            skip_len_253: tryte = 0
    match id <=> 254:
        0:
            return 7
        -1:
            skip_len_254: tryte = 0
        1:
            skip_len_254: tryte = 0
    match id <=> 255:
        0:
            return 6
        -1:
            skip_len_255: tryte = 0
        1:
            skip_len_255: tryte = 0
    return 0

fn main() -> tryte:
    mut buffer: tryte[512] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    mut cursor: tryte = 0
    mut offset: tryte = 0
    mut length: tryte = 0

    length = text_length(1)
    offset = 0
    buffer[cursor] = text_byte_at(1, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(1, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(1, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(1, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(1, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(1, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(102)
    offset = 0
    buffer[cursor] = text_byte_at(102, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(102, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(102, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(102, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(102, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(2)
    offset = 0
    buffer[cursor] = text_byte_at(2, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(2, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(2, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(2, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(2, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(2, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(2, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(2, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(2, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(100)
    offset = 0
    buffer[cursor] = text_byte_at(100, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(100, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(100, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(100, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(6)
    offset = 0
    buffer[cursor] = text_byte_at(6, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(6, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(12)
    offset = 0
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(3)
    offset = 0
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(300)
    offset = 0
    buffer[cursor] = text_byte_at(300, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(300, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(8)
    offset = 0
    buffer[cursor] = text_byte_at(8, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(12)
    offset = 0
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(3)
    offset = 0
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(301)
    offset = 0
    buffer[cursor] = text_byte_at(301, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(301, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(8)
    offset = 0
    buffer[cursor] = text_byte_at(8, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(12)
    offset = 0
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(3)
    offset = 0
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(302)
    offset = 0
    buffer[cursor] = text_byte_at(302, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(302, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(8)
    offset = 0
    buffer[cursor] = text_byte_at(8, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(12)
    offset = 0
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(3)
    offset = 0
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(303)
    offset = 0
    buffer[cursor] = text_byte_at(303, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(303, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(8)
    offset = 0
    buffer[cursor] = text_byte_at(8, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(12)
    offset = 0
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(3)
    offset = 0
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(304)
    offset = 0
    buffer[cursor] = text_byte_at(304, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(304, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(8)
    offset = 0
    buffer[cursor] = text_byte_at(8, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(12)
    offset = 0
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(3)
    offset = 0
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(3, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(305)
    offset = 0
    buffer[cursor] = text_byte_at(305, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(305, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(8)
    offset = 0
    buffer[cursor] = text_byte_at(8, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(12)
    offset = 0
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(12, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(4)
    offset = 0
    buffer[cursor] = text_byte_at(4, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(4, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(4, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(4, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(4, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(4, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(101)
    offset = 0
    buffer[cursor] = text_byte_at(101, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(101, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(101, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(101, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(101, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(200)
    offset = 0
    buffer[cursor] = text_byte_at(200, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(200, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(200, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(200, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(200, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(200, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(300)
    offset = 0
    buffer[cursor] = text_byte_at(300, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(300, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(8)
    offset = 0
    buffer[cursor] = text_byte_at(8, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(240)
    offset = 0
    buffer[cursor] = text_byte_at(240, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(240, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(9)
    offset = 0
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(250)
    offset = 0
    buffer[cursor] = text_byte_at(250, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(250, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(250, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(250, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(250, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(250, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(250, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(201)
    offset = 0
    buffer[cursor] = text_byte_at(201, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(201, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(201, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(201, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(301)
    offset = 0
    buffer[cursor] = text_byte_at(301, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(301, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(8)
    offset = 0
    buffer[cursor] = text_byte_at(8, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(300)
    offset = 0
    buffer[cursor] = text_byte_at(300, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(300, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(9)
    offset = 0
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(251)
    offset = 0
    buffer[cursor] = text_byte_at(251, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(251, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(251, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(251, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(251, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(251, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(200)
    offset = 0
    buffer[cursor] = text_byte_at(200, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(200, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(200, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(200, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(200, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(200, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(302)
    offset = 0
    buffer[cursor] = text_byte_at(302, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(302, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(8)
    offset = 0
    buffer[cursor] = text_byte_at(8, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(241)
    offset = 0
    buffer[cursor] = text_byte_at(241, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(9)
    offset = 0
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(252)
    offset = 0
    buffer[cursor] = text_byte_at(252, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(252, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(252, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(252, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(252, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(252, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(252, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(201)
    offset = 0
    buffer[cursor] = text_byte_at(201, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(201, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(201, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(201, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(303)
    offset = 0
    buffer[cursor] = text_byte_at(303, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(303, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(8)
    offset = 0
    buffer[cursor] = text_byte_at(8, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(302)
    offset = 0
    buffer[cursor] = text_byte_at(302, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(302, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(9)
    offset = 0
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(253)
    offset = 0
    buffer[cursor] = text_byte_at(253, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(253, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(253, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(253, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(253, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(253, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(202)
    offset = 0
    buffer[cursor] = text_byte_at(202, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(202, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(202, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(202, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(304)
    offset = 0
    buffer[cursor] = text_byte_at(304, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(304, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(8)
    offset = 0
    buffer[cursor] = text_byte_at(8, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(303)
    offset = 0
    buffer[cursor] = text_byte_at(303, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(303, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(9)
    offset = 0
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(254)
    offset = 0
    buffer[cursor] = text_byte_at(254, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(254, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(254, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(254, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(254, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(254, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(254, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(203)
    offset = 0
    buffer[cursor] = text_byte_at(203, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(203, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(203, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(203, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(305)
    offset = 0
    buffer[cursor] = text_byte_at(305, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(305, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(8)
    offset = 0
    buffer[cursor] = text_byte_at(8, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(301)
    offset = 0
    buffer[cursor] = text_byte_at(301, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(301, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(8)
    offset = 0
    buffer[cursor] = text_byte_at(8, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(304)
    offset = 0
    buffer[cursor] = text_byte_at(304, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(304, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(9)
    offset = 0
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(255)
    offset = 0
    buffer[cursor] = text_byte_at(255, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(255, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(255, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(255, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(255, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(255, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(204)
    offset = 0
    buffer[cursor] = text_byte_at(204, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(204, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(204, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(204, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(305)
    offset = 0
    buffer[cursor] = text_byte_at(305, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(305, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(7)
    offset = 0
    buffer[cursor] = text_byte_at(7, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(9)
    offset = 0
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(9, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(255)
    offset = 0
    buffer[cursor] = text_byte_at(255, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(255, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(255, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(255, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(255, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(255, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(5)
    offset = 0
    buffer[cursor] = text_byte_at(5, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(5, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(5, offset)
    cursor = cursor + 1
    offset = offset + 1
    buffer[cursor] = text_byte_at(5, offset)
    cursor = cursor + 1
    offset = offset + 1
    length = text_length(10)
    offset = 0
    buffer[cursor] = text_byte_at(10, offset)
    cursor = cursor + 1
    offset = offset + 1
    return cursor