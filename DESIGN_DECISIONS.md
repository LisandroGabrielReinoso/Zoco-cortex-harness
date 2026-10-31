# Decisiones de diseño: Zoco Canchas + Chat + PDV + Pagos

Usaría el mismo harness y cada herramienta declara su permiso (`canchas:read`, `reservas:write`, `pagos:write`) y si lee o escribe. Ninguna cambia precios, el agente solo propone

El flujo sería: el agente encuentra el turno libre y arma la oferta, el dueño la aprueba, el cliente acepta, se hace la reserva provisoria, se manda el link de pago y la reserva se confirma con el estado `pago_confirmado`

La oferta guarda su estado y versión en la base, así si se reinicia el proceso sigue donde quedó 

## Datos a consultar

- Turnos libres de hoy desde Canchas, con precio de lista y la versión del turno
- Costo del turno desde el PDV, para el margen
- Descuento máximo y quién aprueba, en la configuración del complejo, no en el prompt
- Si el cliente acepta que lo contacten

## Eventos para evitar sobreventa

El turno se puede vender en el mostrador mientras el agente arma la oferta. Canchas manda `turno_reservado` con la versión nueva y antes de ofrecer y de cobrar el agente vuelve a leer la versión, si cambió no ofrece nada, igual que con `operator_took_over`

La reserva es una escritura con condiciones que solo pasa si el turno sigue libre en esa versión, como el bloqueo de la memoria. Queda provisional y si no se paga a tiempo se libera

## Cálculos 

El modelo solo propone el porcentaje y redacta, los números los saca el código

- `descuento ≤ descuento_maximo` 10%, si el modelo propone más se rechaza 
- `precio_final = redondear(precio_lista × (1 − descuento))`
- `margen = precio_final − costo`, y si queda negativo no se ofrece
- `vence = hora_del_turno − anticipación mínima`, después de eso la oferta ya no se manda
- Turno disponible solo si está libre, en la versión leída y empieza después de ahora

## Aprobación humana

La oferta queda como borrador hasta que el dueño la aprueba desde Chat, y la aprobación vale para esos datos exactos, si cambia el precio o el turno hay que aprobar de vuelta. Si el dueño no contesta a tiempo, un `followup_due` la cancela

Si un operador toma la conversación, la oferta queda en la ficha y el agente no la manda ni reserva

## Confirmación del cobro

El link de pago lleva `operation_id` para que un reintento no cobre dos veces. La reserva se confirma solo con `pago_confirmado` de Pagos y nunca porque el cliente diga que pagó. Si el cobro da timeout primero se concilia y después se decide. En las trazas queda el `operation_id` pero nunca el link ni datos de la tarjeta

## Cómo se mediria

Con las trazas se arma el conjunto de ofertas preparadas, aprobadas, aceptadas y pagadas. Para saber si son reservas adicionales se deja un grupo de turnos sin oferta y se las compara, así no se cuentan ventas que iban a pasar igual. El margen es lo cobrado menos el costo, comparado con ese grupo. Sobreventas, ofertas sin aprobar y cobros duplicados tienen que dar 0