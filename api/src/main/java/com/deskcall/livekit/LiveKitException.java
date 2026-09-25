package com.deskcall.livekit;

public class LiveKitException extends RuntimeException {

    public LiveKitException(String message) {
        super(message);
    }

    public LiveKitException(String message, Throwable cause) {
        super(message, cause);
    }
}
