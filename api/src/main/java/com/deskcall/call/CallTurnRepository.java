package com.deskcall.call;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

public interface CallTurnRepository extends JpaRepository<CallTurn, Long> {

    List<CallTurn> findByCallIdOrderBySeqAsc(Long callId);
}
