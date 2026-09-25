package com.deskcall.call;

import com.deskcall.call.CallDtos.CallView;
import com.deskcall.call.CallDtos.CreateCallRequest;
import com.deskcall.call.CallDtos.CreateCallResponse;
import com.deskcall.call.CallDtos.EventRequest;
import com.deskcall.call.CallDtos.PagedResponse;
import com.deskcall.call.CallDtos.ResultRequest;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/calls")
public class CallController {

    private final CallService service;

    public CallController(CallService service) {
        this.service = service;
    }

    /** Buat panggilan: room LiveKit + dispatch agent + token untuk nasabah. */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public CreateCallResponse create(@Valid @RequestBody CreateCallRequest request) {
        return service.create(request);
    }

    @GetMapping("/{callId}")
    public CallView get(@PathVariable String callId,
                        @RequestParam(defaultValue = "false") boolean includeTranscript) {
        return service.get(callId, includeTranscript);
    }

    @GetMapping
    public PagedResponse<CallView> list(@RequestParam(required = false) String externalLoanId,
                                        @RequestParam(required = false) String externalCustomerId,
                                        @RequestParam(required = false) CallStatus status,
                                        @RequestParam(required = false) CallTag tag,
                                        @RequestParam(defaultValue = "0") @Min(0) int page,
                                        @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return service.search(externalLoanId, externalCustomerId, status, tag, page, size);
    }

    /** Event lifecycle dari agent / backend (joined, declined, unreachable, left). */
    @PostMapping("/{callId}/events")
    public CallView event(@PathVariable String callId, @Valid @RequestBody EventRequest request) {
        return service.recordEvent(callId, request);
    }

    /** Hasil akhir percakapan dari agent (tag, PTP, transkrip). */
    @PostMapping("/{callId}/result")
    public CallView result(@PathVariable String callId, @Valid @RequestBody ResultRequest request) {
        return service.submitResult(callId, request);
    }
}
