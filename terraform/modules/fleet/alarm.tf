# Email alert when the load balancer reports an unhealthy backend.

# Topic: where alerts are published. The email subscription listens to it.
resource "oci_ons_notification_topic" "alerts" {
  compartment_id = var.compartment_id
  name           = "gateway-lab-alerts"
  description    = "Alerts for the gateway lab"
}

# Email subscription. OCI sends a confirmation email first; the subscription
# stays pending until the link in it is clicked.
resource "oci_ons_subscription" "email" {
  compartment_id = var.compartment_id
  topic_id       = oci_ons_notification_topic.alerts.id
  protocol       = "EMAIL"
  endpoint       = var.alarm_email
}

locals {
  # Metric name as written on Oracle's Load Balancer metrics page (oci_lbaas
  # namespace). Names in alarm queries are case-sensitive.
  unhealthy_backend_metric = "unhealthyBackendServers"
}

# Alarm: any unhealthy backend in this load balancer, for 1 minute. The metric
# is emitted every 60 seconds, so a 1 minute window is the finest that fits.
resource "oci_monitoring_alarm" "unhealthy_backend" {
  compartment_id        = var.compartment_id
  metric_compartment_id = var.compartment_id
  display_name          = "gateway-lab-unhealthy-backend"
  namespace             = "oci_lbaas"
  query                 = "${local.unhealthy_backend_metric}[1m]{resourceId = \"${oci_load_balancer_load_balancer.main.id}\"}.max() > 0"
  severity              = "CRITICAL"
  pending_duration      = "PT1M"
  is_enabled            = true
  destinations          = [oci_ons_notification_topic.alerts.id]
  body                  = "The gateway lab load balancer reports an unhealthy backend. Start with the runbooks in docs/runbooks."
}
