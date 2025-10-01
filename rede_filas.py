import heapq
from typing import Dict, List, Tuple, Optional, Callable
from gerador import LinearCongruentialGenerator
from dataclasses import dataclass, field

# ---------------------------
#  Estruturas de Dados
# ---------------------------

ARRIVAL = "ARRIVAL"
DEPARTURE = "DEPARTURE"

@dataclass(order=True)
class Event:
    time: float
    seq: int
    etype: str
    node_name: str = field(compare=False)

@dataclass
class Node:
    name: str
    c: int  #servidores
    k: int  #capacidade total (fila + serviço)
    service_sampler: Callable[[], float]
    arrival_sampler: Optional[Callable[[], float]] = None

    n: int = 0
    tempo_estado: List[float] = field(default_factory=list)
    atendidos: int = 0
    perdas: int = 0

    def __post_init__(self):
        self.tempo_estado = [0.0 for _ in range(self.k + 1)]

    def admit(self) -> bool:
        if self.n >= self.k:
            self.perdas += 1
            return False
        self.n += 1
        return True

    def start_service_if_possible(self) -> bool:
        #em G/G/c/K, um cliente está esperando se n > c
        if self.n > self.c:
            #verifica se há mais clientes no sistema do que servidores
            return True
        return False

    def finish_service_one(self):
        """Finaliza o serviço de um cliente."""
        self.n -= 1
        self.atendidos += 1

# ---------------------------
#  Gerenciador de Aleatórios
# ---------------------------

class SimulationRNG:
    def __init__(self, config: Dict):
        if 'rndnumbers' in config and not 'seeds' in config:
            self.numbers = iter(config['rndnumbers'])
            self.source = 'list'
        else:
            seed = config.get('seed', 1)
            self.lcg = LinearCongruentialGenerator(seed=seed)
            self.source = 'lcg'
        self.used = 0

    def u(self) -> float:
        #retorna o próximo random U(0,1)
        self.used += 1
        if self.source == 'list':
            try:
                return next(self.numbers)
            except StopIteration:
                raise RuntimeError("Lista de números aleatórios esgotada.")
        else:
            return self.lcg.next_random()

# ---------------------------
#  Simulador da Rede
# ---------------------------

class NetworkSimulator:
    def __init__(self, config: Dict):
        self.rng = SimulationRNG(config)
        self.nodes: Dict[str, Node] = {}
        self.routing_table: Dict[str, List[Tuple[str, float]]] = {}
        self.total_arrivals_target = 0
        self.total_arrivals_count = 0

        self._build_network(config)

        self.time = 0.0
        self.last_update_time = 0.0
        self.events: List[Event] = []
        self.seq_counter = 0

    def _make_sampler(self, min_val: float, max_val: float) -> Callable[[], float]:
        #distruibuição uniforme
        def sample():
            return min_val + (max_val - min_val) * self.rng.u()
        return sample

    def _build_network(self, config: Dict):
        for name, params in config.get('queues', {}).items():
            service_sampler = self._make_sampler(params['minService'], params['maxService'])
            arrival_sampler = None
            if 'minArrival' in params and 'maxArrival' in params:
                arrival_sampler = self._make_sampler(params['minArrival'], params['maxArrival'])
            
            capacity = int(params.get('capacity', float('inf')))

            self.nodes[name] = Node(
                name=name,
                c=int(params['servers']),
                k=capacity,
                service_sampler=service_sampler,
                arrival_sampler=arrival_sampler
            )

        raw_routing = {}
        for rule in config.get('network', []):
            source = rule['source']
            target = rule['target']
            prob = float(rule['probability'])
            if source not in raw_routing:
                raw_routing[source] = []
            raw_routing[source].append({'target': target, 'prob': prob})
        
        for source, destinations in raw_routing.items():
            #da sort por probabilidade
            destinations.sort(key=lambda x: x['prob'])
            self.routing_table[source] = []
            cumulative_prob = 0.0
            for dest in destinations:
                cumulative_prob += dest['prob']
                self.routing_table[source].append((dest['target'], cumulative_prob))

        arrivals_config = config.get('arrivals', {})
        self.total_arrivals_target = sum(int(v) for v in arrivals_config.values())

    def schedule(self, time: float, etype: str, node_name: str):
        self.seq_counter += 1
        event = Event(time=time, seq=self.seq_counter, etype=etype, node_name=node_name)
        heapq.heappush(self.events, event)

    def update_time_stats(self, t_new: float):
       #acumula o tempo gasto em cada estado para todos os nodos
        dt = t_new - self.last_update_time
        if dt > 0:
            for node in self.nodes.values():
                node.tempo_estado[node.n] += dt
        self.last_update_time = t_new

    def pick_destination(self, source_node_name: str) -> Optional[str]:
        #sorteia um destino para um cliente a partir de uim nodo origem
        rules = self.routing_table.get(source_node_name)
        if not rules:
            return None

        u = self.rng.u()
        for target, cumulative_prob in rules:
            if u < cumulative_prob:
                return target
        
        return None #saída do sistema se u for maior que a soma das probabilidades

    def run(self):
        #agendando as primeiras chegadas externas
        for name, node in self.nodes.items():
            if node.arrival_sampler:
                first_arrival_time = node.arrival_sampler()
                self.schedule(first_arrival_time, ARRIVAL, name)

        while self.events and (self.total_arrivals_target == 0 or self.total_arrivals_count < self.total_arrivals_target):
            ev = heapq.heappop(self.events)
            self.update_time_stats(ev.time)
            self.time = ev.time
            
            fila_origem = self.nodes[ev.node_name]

            if ev.etype == ARRIVAL:
                self.total_arrivals_count += 1
                
                #agenda prox chegada externa partindo daqu
                if fila_origem.arrival_sampler:
                    next_ia = fila_origem.arrival_sampler()
                    self.schedule(self.time + next_ia, ARRIVAL, fila_origem.name)

                #processa a chegada do cliente na fila_origem
                if fila_origem.admit():
                    if fila_origem.n <= fila_origem.c: # Se houver servidor livre
                        service_time = fila_origem.service_sampler()
                        self.schedule(self.time + service_time, DEPARTURE, fila_origem.name)

            elif ev.etype == DEPARTURE:
                fila_origem.finish_service_one()

                if fila_origem.n >= fila_origem.c:
                    service_time = fila_origem.service_sampler()
                    self.schedule(self.time + service_time, DEPARTURE, fila_origem.name)

                dest_name = self.pick_destination(fila_origem.name)
                if dest_name:
                    fila_destino = self.nodes[dest_name]
                    if fila_destino.admit():
                        if fila_destino.n <= fila_destino.c: # Se servidor livre no destino
                            service_time = fila_destino.service_sampler()
                            self.schedule(self.time + service_time, DEPARTURE, fila_destino.name)

        self.update_time_stats(self.time) #att final
        return self._get_results()

    def _get_results(self) -> Dict:
        results = {
            "tempo_global": self.time,
            "randoms_usados": self.rng.used,
            "chegadas_totais": self.total_arrivals_count,
            "filas": {}
        }
        for name, node in self.nodes.items():
            total_time = sum(node.tempo_estado)
            results["filas"][name] = {
                "servidores": node.c,
                "capacidade": node.k,
                "atendidos": node.atendidos,
                "perdas": node.perdas,
                "tempo_estado": node.tempo_estado,
                "prob_estado": [t / total_time if total_time > 0 else 0 for t in node.tempo_estado]
            }
        return results