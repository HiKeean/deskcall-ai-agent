package com.deskcall.call;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import com.deskcall.call.CallDtos.CallView;
import com.deskcall.call.CallDtos.CreateCallRequest;
import com.deskcall.call.CallDtos.CreateCallResponse;
import com.deskcall.call.CallDtos.EventRequest;
import com.deskcall.call.CallDtos.EventView;
import com.deskcall.call.CallDtos.PagedResponse;
import com.deskcall.call.CallDtos.ResultRequest;
import com.deskcall.call.CallDtos.TurnRequest;
import com.deskcall.call.CallDtos.TurnView;
import com.deskcall.config.DeskcallProperties;
import com.deskcall.livekit.LiveKitClient;
import com.deskcall.livekit.LiveKitException;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import jakarta.persistence.criteria.Predicate;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.server.ResponseStatusException;

@Service
public class CallService {

    private static final Logger log = LoggerFactory.getLogger(CallService.class);
    private static final String CUSTOMER_IDENTITY = "customer";
    private static final List<String> ACTIVE_STATUSES = List.of(CallStatus.CREATED.name(), CallStatus.ANSWERED.name());

    private final CallRepository calls;
    private final CallEventRepository events;
    private final CallTurnRepository turns;
    private final LiveKitClient liveKit;
    private final DeskcallProperties props;
    private final Clock clock;
    private final ObjectMapper mapper;
    private final TransactionTemplate tx;

    public CallService(CallRepository calls, CallEventRepository events, CallTurnRepository turns,
                       LiveKitClient liveKit, DeskcallProperties props, Clock clock, ObjectMapper mapper,
                       TransactionTemplate tx) {
        this.calls = calls;
        this.events = events;
        this.turns = turns;
        this.liveKit = liveKit;
        this.props = props;
        this.clock = clock;
        this.mapper = mapper;
        this.tx = tx;
    }

    // --- buat panggilan ---

    public CreateCallResponse create(CreateCallRequest r) {
        boolean undisclosed = Boolean.FALSE.equals(r.discloseAi());
        if (undisclosed && !props.call().allowUndisclosedOpening()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "discloseAi=false is only allowed in demo environments (DESKCALL_ALLOW_DEMO_OPENING=true)");
        }
        if (undisclosed) {
            log.warn("Call created with discloseAi=false (demo opening) for loan {}", r.externalLoanId());
        }
        if (r.externalLoanId() != null && calls.existsByExternalLoanIdAndStatusIn(r.externalLoanId(), ACTIVE_STATUSES)) {
            throw new ConflictException("ACTIVE_CALL_EXISTS", "There is already an active call for this loan");
        }
        String uid = UUID.randomUUID().toString();
        String room = props.livekit().roomPrefix() + uid;

        Call call = tx.execute(s -> {
            LocalDateTime now = now();
            Call c = calls.save(new Call(uid, r.externalCustomerId(), r.externalLoanId(), r.customerName(),
                    r.installmentAmount(), r.penaltyAmount(), r.dueDate(), room, now));
            events.save(new CallEvent(c.getId(), "CREATED", null, now));
            return c;
        });

        try {
            liveKit.createRoom(room);
            String dispatchId = liveKit.createAgentDispatch(room, props.livekit().agentName(), agentMetadata(uid, r));
            LiveKitClient.CustomerToken token = liveKit.issueCustomerToken(room, CUSTOMER_IDENTITY, r.customerName());
            events.save(new CallEvent(call.getId(), "DISPATCHED", "dispatch=" + dispatchId, now()));
            return new CreateCallResponse(uid, CallStatus.CREATED, room, liveKit.url(), CUSTOMER_IDENTITY,
                    token.token(), token.expiresAt(), props.call().ringTimeoutSeconds());
        } catch (LiveKitException e) {
            log.warn("Failed to prepare call {}: {}", uid, e.getMessage());
            tx.executeWithoutResult(s -> {
                Call c = calls.findById(call.getId()).orElseThrow();
                LocalDateTime now = now();
                c.markFailed("Gagal menyiapkan panggilan: " + e.getMessage(), now);
                calls.save(c);
                events.save(new CallEvent(c.getId(), "FAILED", e.getMessage(), now));
            });
            cleanupRoom(room);
            throw e;
        }
    }

    /** Konteks untuk agent (snake_case, sama dengan CallContext di agent/). Hanya lewat dispatch, tidak disimpan. */
    private String agentMetadata(String uid, CreateCallRequest r) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("call_id", uid);
        m.put("customer_name", r.customerName());
        m.put("ai_name", r.aiName());
        m.put("company_name", r.companyName());
        m.put("installment_amount", r.installmentAmount());
        m.put("penalty_amount", r.penaltyAmount());
        m.put("due_date", r.dueDate().toString());
        putIfPresent(m, "autodebet_cutoff", r.autodebetCutoff());
        putIfPresent(m, "closing_magic_words", r.closingMagicWords());
        putIfPresent(m, "birth_date", r.birthDate() == null ? null : r.birthDate().toString());
        putIfPresent(m, "address", r.address());
        putIfPresent(m, "max_promise_days", r.maxPromiseDays());
        if (Boolean.FALSE.equals(r.discloseAi())) {
            m.put("disclose_ai", false);
        }
        putIfPresent(m, "external_customer_id", r.externalCustomerId());
        putIfPresent(m, "external_loan_id", r.externalLoanId());
        try {
            return mapper.writeValueAsString(m);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Cannot serialize agent metadata", e);
        }
    }

    private static void putIfPresent(Map<String, Object> m, String key, Object value) {
        if (value != null && !(value instanceof String s && s.isBlank())) {
            m.put(key, value);
        }
    }

    // --- baca ---

    public CallView get(String callUid, boolean includeTranscript) {
        Call c = getOrThrow(callUid);
        return view(c, true, includeTranscript);
    }

    public PagedResponse<CallView> search(String externalLoanId, String externalCustomerId, CallStatus status,
                                          CallTag tag, int page, int size) {
        Specification<Call> spec = (root, query, cb) -> {
            List<Predicate> p = new ArrayList<>();
            if (externalLoanId != null) p.add(cb.equal(root.get("externalLoanId"), externalLoanId));
            if (externalCustomerId != null) p.add(cb.equal(root.get("externalCustomerId"), externalCustomerId));
            if (status != null) p.add(cb.equal(root.get("status"), status.name()));
            if (tag != null) p.add(cb.equal(root.get("tag"), tag.name()));
            return cb.and(p.toArray(new Predicate[0]));
        };
        Page<Call> result = calls.findAll(spec, PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "id")));
        List<CallView> items = result.getContent().stream().map(c -> view(c, false, false)).toList();
        return new PagedResponse<>(items, page, size, result.getTotalElements(), result.getTotalPages());
    }

    // --- event lifecycle ---

    public CallView recordEvent(String callUid, EventRequest req) {
        boolean[] closed = {false};
        Call call = tx.execute(s -> {
            Call c = getOrThrow(callUid);
            LocalDateTime now = now();
            events.save(new CallEvent(c.getId(), req.type().name(), req.detail(), now));
            CallStatus status = c.getStatus();
            switch (req.type()) {
                case CUSTOMER_JOINED -> {
                    if (status == CallStatus.CREATED) {
                        c.markAnswered(now);
                    }
                }
                case CUSTOMER_DECLINED -> {
                    if (status == CallStatus.CREATED) {
                        c.markEnded(CallTag.NSTD, "nasabah menolak panggilan", now);
                        closed[0] = true;
                    }
                }
                case UNREACHABLE -> {
                    if (status == CallStatus.CREATED) {
                        c.markEnded(CallTag.CBR, req.detail() != null ? req.detail() : "panggilan tidak dapat sampai", now);
                        closed[0] = true;
                    }
                }
                case CUSTOMER_LEFT -> {
                    if (status == CallStatus.ANSWERED && c.getResultReceivedAt() == null) {
                        c.markEnded(CallTag.OTHERS, "nasabah keluar sebelum percakapan selesai", now);
                        closed[0] = true;
                    }
                }
                case AGENT_JOINED -> {
                }
            }
            return calls.save(c);
        });
        if (closed[0]) {
            cleanupRoom(call.getRoomName());
        }
        return view(call, true, false);
    }

    // --- hasil dari agent ---

    public CallView submitResult(String callUid, ResultRequest req) {
        if (req.tag() == CallTag.PTP && req.ptpDate() == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "ptpDate is required when tag is PTP");
        }
        if (req.tag() != CallTag.PTP && req.ptpDate() != null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "ptpDate is only allowed when tag is PTP");
        }
        Call call = tx.execute(s -> {
            Call c = getOrThrow(callUid);
            if (c.getResultReceivedAt() != null) {
                throw new ConflictException("RESULT_ALREADY_RECEIVED", "Result was already submitted for this call");
            }
            if (c.getStatus() == CallStatus.FAILED) {
                throw new ConflictException("CALL_FAILED", "Call failed to start; no result accepted");
            }
            LocalDateTime now = now();
            c.applyResult(req.tag(), req.verified(), req.ptpDate(), req.note(), now);
            calls.save(c);
            if (req.transcript() != null) {
                List<CallTurn> rows = new ArrayList<>();
                int seq = 1;
                for (TurnRequest t : req.transcript()) {
                    rows.add(new CallTurn(c.getId(), seq++, t.speaker(), t.text(), t.state()));
                }
                turns.saveAll(rows);
            }
            String states = req.statesVisited() == null ? null : "states=" + String.join(",", req.statesVisited());
            events.save(new CallEvent(c.getId(), "RESULT_RECEIVED", states, now));
            return c;
        });
        cleanupRoom(call.getRoomName());
        return view(call, true, true);
    }

    // --- sweeper ---

    /** Belum di-accept setelah ring timeout -> NSTD. */
    public int expireUnanswered() {
        LocalDateTime cutoff = now().minusSeconds(props.call().ringTimeoutSeconds());
        int n = 0;
        for (Call c : calls.findByStatusAndCreatedAtBefore(CallStatus.CREATED.name(), cutoff)) {
            if (endIfStill(c.getId(), CallStatus.CREATED, CallTag.NSTD, "RING_TIMEOUT",
                    "tidak diangkat sampai time-out")) {
                n++;
            }
        }
        return n;
    }

    /** Sudah di-accept tapi tidak ada hasil setelah durasi maksimal -> OTHERS. */
    public int expireOverdue() {
        LocalDateTime cutoff = now().minusSeconds(props.call().maxDurationSeconds());
        int n = 0;
        for (Call c : calls.findByStatusAndAnsweredAtBefore(CallStatus.ANSWERED.name(), cutoff)) {
            if (endIfStill(c.getId(), CallStatus.ANSWERED, CallTag.OTHERS, "DURATION_TIMEOUT",
                    "melewati durasi maksimal tanpa hasil")) {
                n++;
            }
        }
        return n;
    }

    private boolean endIfStill(Long id, CallStatus expected, CallTag tag, String eventType, String note) {
        try {
            Call ended = tx.execute(s -> {
                Call c = calls.findById(id).orElse(null);
                if (c == null || c.getStatus() != expected) {
                    return null;
                }
                LocalDateTime now = now();
                c.markEnded(tag, note, now);
                calls.save(c);
                events.save(new CallEvent(id, eventType, null, now));
                return c;
            });
            if (ended == null) {
                return false;
            }
            cleanupRoom(ended.getRoomName());
            return true;
        } catch (ObjectOptimisticLockingFailureException e) {
            return false; // sudah diubah proses lain (event/result), biarkan
        }
    }

    // --- helper ---

    private Call getOrThrow(String callUid) {
        return calls.findByCallUid(callUid).orElseThrow(() -> new NotFoundException("Call not found: " + callUid));
    }

    private LocalDateTime now() {
        return LocalDateTime.now(clock);
    }

    private void cleanupRoom(String room) {
        try {
            liveKit.deleteRoom(room);
        } catch (LiveKitException e) {
            log.warn("Room cleanup failed for {}: {}", room, e.getMessage());
        }
    }

    private CallView view(Call c, boolean withEvents, boolean withTranscript) {
        List<EventView> eventViews = withEvents
                ? events.findByCallIdOrderByIdAsc(c.getId()).stream()
                .map(e -> new EventView(e.getType(), e.getDetail(), instant(e.getOccurredAt()))).toList()
                : null;
        List<TurnView> turnViews = withTranscript
                ? turns.findByCallIdOrderBySeqAsc(c.getId()).stream()
                .map(t -> new TurnView(t.getSeq(), t.getSpeaker(), t.getContent(), t.getState())).toList()
                : null;
        return new CallView(c.getCallUid(), c.getExternalCustomerId(), c.getExternalLoanId(), c.getCustomerName(),
                c.getStatus(), c.getTag(), c.isVerified(), c.getPtpDate(), c.getNote(), c.getRoomName(),
                instant(c.getCreatedAt()), instant(c.getAnsweredAt()), instant(c.getEndedAt()), eventViews, turnViews);
    }

    private static Instant instant(LocalDateTime t) {
        return t == null ? null : t.toInstant(ZoneOffset.UTC);
    }
}
