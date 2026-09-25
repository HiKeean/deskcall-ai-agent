package com.deskcall.call;

public enum CallStatus {
    /** Room + dispatch siap, menunggu nasabah accept (ringing). */
    CREATED,
    /** Nasabah sudah join room. */
    ANSWERED,
    /** Selesai; tag terisi. */
    ENDED,
    /** Gagal menyiapkan panggilan di sisi sistem (mis. LiveKit tidak terjangkau). */
    FAILED
}
