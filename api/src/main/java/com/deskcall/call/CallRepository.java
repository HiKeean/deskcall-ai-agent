package com.deskcall.call;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface CallRepository extends JpaRepository<Call, Long>, JpaSpecificationExecutor<Call> {

    Optional<Call> findByCallUid(String callUid);

    boolean existsByExternalLoanIdAndStatusIn(String externalLoanId, Collection<String> statuses);

    List<Call> findByStatusAndCreatedAtBefore(String status, LocalDateTime before);

    List<Call> findByStatusAndAnsweredAtBefore(String status, LocalDateTime before);
}
