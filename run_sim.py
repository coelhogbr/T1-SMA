import sys
import json
from pathlib import Path
from rede_filas import NetworkSimulator

def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {path}")

    lines = [line for line in p.read_text().splitlines() if not line.strip().startswith(('#', '!'))]
    
    try:
        import yaml
        return yaml.safe_load("\n".join(lines))
    except ImportError:
        print("A biblioteca PyYAML não está instalada. Tente 'pip install pyyaml'.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Erro ao parsear o arquivo YAML: {e}")
        sys.exit(1)

def print_results(results: dict, seed: int = None):
    if seed:
        print(f"\n--- RESULTADOS PARA SEMENTE: {seed} ---")
    
    print(f"Simulação encerrada no tempo: {results['tempo_global']:.4f}")
    print(f"Números aleatórios utilizados: {results['randoms_usados']}")
    print(f"Total de chegadas externas processadas: {results['chegadas_totais']}")

    for name, data in results["filas"].items():
        print(f"\nFila: {name} (servidores={data['servidores']}, capacidade={data['capacidade']})")
        print(f"  Clientes atendidos: {data['atendidos']}")
        print(f"  Perdas por capacidade: {data['perdas']}")
        print("  Probabilidade de ocupação:")
        for i, prob in enumerate(data['prob_estado']):
            if prob > 1e-6: # Apenas mostra estados que ocorreram
                print(f"    P({i} clientes) = {prob*100:.2f}%")

def main():
    if len(sys.argv) < 2:
        print("Uso: python run_sim.py <arquivo_modelo.yml>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    config = load_config(config_path)

    if 'seeds' in config:
        all_results = {}
        for seed in config['seeds']:
            run_config = config.copy()
            run_config['seed'] = seed
            sim = NetworkSimulator(run_config)
            results = sim.run()
            print_results(results, seed)
            all_results[f"seed_{seed}"] = results
        
        out_path = Path(config_path).with_suffix(".results.json")
        Path(out_path).write_text(json.dumps(all_results, indent=2))
        print(f"\nResultados de todas as sementes salvos em: {out_path}")

    else:
        sim = NetworkSimulator(config)
        results = sim.run()
        print_results(results)
        
        out_path = Path(config_path).with_suffix(".result.json")
        Path(out_path).write_text(json.dumps(results, indent=2))
        print(f"\nResultados salvos em: {out_path}")

if __name__ == "__main__":
    main()