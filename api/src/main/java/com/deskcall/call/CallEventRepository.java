package com.deskcall.call;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

public interface CallEventRepository extends JpaRepository<CallEvent, Long> {

    List<CallEvent> findByCallIdOrderByIdAsc(Long callId);
}
