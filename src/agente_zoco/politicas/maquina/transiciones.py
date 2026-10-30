#Función de transición δ: (estado, evento) -> (estado nuevo, actores que pueden disparar el evento)

TRANSICIONES = {
    ("AUTO", "operator_takeover"): ("HUMAN", {"operador"}),
    ("AUTO", "customer_requests_human"): ("HUMAN", {"cliente"}),
    ("AUTO", "low_confidence"): ("SUGGEST", {"sistema"}),
    ("AUTO", "abuse_detected"): ("BLOCKED", {"sistema", "operador"}),

    ("SUGGEST", "operator_takeover"): ("HUMAN", {"operador"}),
    ("SUGGEST", "operator_release"): ("AUTO", {"operador"}),
    ("SUGGEST", "abuse_detected"): ("BLOCKED", {"sistema", "operador"}),
    
    ("HUMAN", "operator_release"): ("AUTO", {"operador"}),
    ("HUMAN", "abuse_detected"): ("BLOCKED", {"operador"}),
    # sin operator_release: de BLOCKED solo saca un supervisor 
    ("BLOCKED", "supervisor_unblock"): ("AUTO", {"supervisor"}),
    # fuera de horario solo responde la IA; 
    ("AUTO", "out_of_hours_started"): ("AUTO", {"sistema"}),
    ("SUGGEST", "out_of_hours_started"): ("AUTO", {"sistema"}),
    ("HUMAN", "out_of_hours_started"): ("AUTO", {"sistema"}),
    ("BLOCKED", "out_of_hours_started"): ("BLOCKED", {"sistema"}),

    # evento que faltaba: vuelve el horario de atención
    ("AUTO", "out_of_hours_ended"): ("AUTO", {"sistema"}),
    ("BLOCKED", "out_of_hours_ended"): ("BLOCKED", {"sistema"}),
}
