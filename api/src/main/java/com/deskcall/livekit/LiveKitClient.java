package com.deskcall.livekit;

import java.time.Instant;

/** Batas ke server LiveKit. Implementasi asli: HttpLiveKitClient; di test diganti mock. */
public interface LiveKitClient {

    /** URL untuk klien (wss://...). */
    String url();

    void createRoom(String roomName);

    /** Dispatch eksplisit agent ke room; metadata hanya dilihat agent, bukan peserta. @return id dispatch. */
    String createAgentDispatch(String roomName, String agentName, String metadataJson);

    void deleteRoom(String roomName);

    CustomerToken issueCustomerToken(String roomName, String identity, String displayName);

    record CustomerToken(String token, Instant expiresAt) {
    }
}
