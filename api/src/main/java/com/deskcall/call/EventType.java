package com.deskcall.call;

/** Event lifecycle yang boleh dilaporkan klien API (agent / backend klarfinance). */
public enum EventType {
    AGENT_JOINED,
    CUSTOMER_JOINED,
    /** Nasabah menolak di layar incoming call -> NSTD. */
    CUSTOMER_DECLINED,
    /** Panggilan tidak bisa sampai (tidak ada token FCM, device offline, app tidak terpasang) -> CBR. */
    UNREACHABLE,
    /** Nasabah keluar room. Kalau belum ada hasil -> OTHERS. */
    CUSTOMER_LEFT
}
