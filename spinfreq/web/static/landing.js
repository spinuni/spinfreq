'use strict';
(async () => {
  try {
    const response = await fetch('/api/capabilities');
    if (!response.ok) throw new Error('Capability check failed');
    const support = await response.json();
    document.getElementById('runtime').textContent = support.experimental ? 'Windows · experimental native computation' : support.simulation_enabled ? 'Linux · local computation available' : 'Configuration preview · simulations disabled on this server';
    document.getElementById('capability').textContent = support.message;
    document.getElementById('launch').textContent = support.simulation_enabled ? 'Open simulator' : 'Explore & export a configuration';
  } catch (error) {
    document.getElementById('runtime').textContent = 'Cannot determine execution capabilities. Please reload.';
  }
})();
