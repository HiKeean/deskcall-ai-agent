package com.deskcall.call;

import java.util.LinkedHashMap;
import java.util.Map;

import com.deskcall.livekit.LiveKitException;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;

@RestControllerAdvice
public class ApiExceptionHandler extends ResponseEntityExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler(NotFoundException.class)
    public ProblemDetail notFound(NotFoundException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, e.getMessage());
    }

    @ExceptionHandler(ConflictException.class)
    public ProblemDetail conflict(ConflictException e) {
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, e.getMessage());
        pd.setProperty("code", e.getCode());
        return pd;
    }

    @ExceptionHandler(ObjectOptimisticLockingFailureException.class)
    public ProblemDetail concurrentUpdate(ObjectOptimisticLockingFailureException e) {
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, "Concurrent update, please retry");
        pd.setProperty("code", "CONCURRENT_UPDATE");
        return pd;
    }

    @ExceptionHandler(LiveKitException.class)
    public ProblemDetail liveKitFailure(LiveKitException e) {
        log.warn("LiveKit failure: {}", e.getMessage());
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_GATEWAY, "LiveKit server is unavailable");
        pd.setProperty("code", "LIVEKIT_UNAVAILABLE");
        return pd;
    }

    @Override
    protected ResponseEntity<Object> handleMethodArgumentNotValid(MethodArgumentNotValidException ex,
                                                                  HttpHeaders headers, HttpStatusCode status,
                                                                  WebRequest request) {
        Map<String, String> errors = new LinkedHashMap<>();
        ex.getBindingResult().getFieldErrors().forEach(f -> errors.putIfAbsent(f.getField(), f.getDefaultMessage()));
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "Validation failed");
        pd.setProperty("errors", errors);
        return handleExceptionInternal(ex, pd, headers, HttpStatus.BAD_REQUEST, request);
    }
}
