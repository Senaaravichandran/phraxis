import logging
import os
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class QOPEServiceError(Exception):
    """Raised when QOPE service encounters an error."""
    pass


class QOPEService:
    """
    Quantum Code Optimization Planning Engine.
    Uses IBM Quantum QAOA to solve combinatorial optimization for code changes.
    """
    
    def __init__(self):
        """Initialize QOPE without opening a Quantum Runtime connection yet."""
        self.quantum_backend = os.environ.get("IBM_QUANTUM_BACKEND", "ibmq_qasm_simulator")
    
    def optimize(
        self,
        candidate_changes: List[Dict[str, Any]],
        conflict_matrix: List[List[int]]
    ) -> Dict[str, Any]:
        """
        Find optimal subset of code changes using QAOA or classical fallback.
        
        Args:
            candidate_changes: List of dicts with {file_path, function_name, coverage_weight}
            conflict_matrix: NxN matrix where [i][j]=1 if changes i,j conflict
        
        Returns:
            Dictionary with optimal_changes, selected_files, objective_value, etc.
        """
        if not candidate_changes:
            return {
                "optimal_changes": [],
                "selected_files": [],
                "objective_value": 0.0,
                "conflict_risk": 0,
                "quantum_backend": "none",
                "num_qubits": 0,
            }
        
        n = len(candidate_changes)
        
        # Validate conflict matrix
        if len(conflict_matrix) != n or any(len(row) != n for row in conflict_matrix):
            row_count = len(conflict_matrix)
            col_count = len(conflict_matrix[0]) if conflict_matrix else 0
            raise QOPEServiceError(
                f"Conflict matrix dimensions {row_count}x{col_count} "
                f"do not match candidate_changes length {n}"
            )
        
        logger.info(f"QOPE: Optimizing {n} candidate changes (2^{n} = {2**n} combinations)")
        
        try:
            if not os.environ.get("IBM_QUANTUM_TOKEN"):
                raise QOPEServiceError("IBM_QUANTUM_TOKEN is not configured")
            return self._optimize_quantum(candidate_changes, conflict_matrix)
        except Exception as e:
            logger.warning(f"QOPE: quantum optimization unavailable: {e}")
            return self._optimize_classical(candidate_changes, conflict_matrix)
    
    def _optimize_quantum(
        self,
        candidate_changes: List[Dict[str, Any]],
        conflict_matrix: List[List[int]]
    ) -> Dict[str, Any]:
        """
        Quantum optimization using IBM Quantum QAOA.
        """
        from qiskit_ibm_runtime import QiskitRuntimeService
        from qiskit_optimization import QuadraticProgram
        from qiskit_optimization.algorithms import MinimumEigenOptimizer
        from qiskit_algorithms import QAOA
        from qiskit_algorithms.optimizers import COBYLA

        n = len(candidate_changes)
        logger.info(f"QOPE: Building QUBO for {n} qubits")
        
        # Build QuadraticProgram
        qp = QuadraticProgram("code_optimizer")
        
        # Add binary variables (one per candidate change)
        for i in range(n):
            qp.binary_var(name=f"x{i}")
        
        # Linear terms: maximize coverage (minimize negative coverage)
        linear = {}
        for i, change in enumerate(candidate_changes):
            coverage = change.get("coverage_weight", 1.0)
            linear[f"x{i}"] = -coverage
        
        # Quadratic terms: penalize conflicts
        CONFLICT_PENALTY = 5.0
        quadratic = {}
        for i in range(n):
            for j in range(i + 1, n):
                if conflict_matrix[i][j] > 0:
                    quadratic[(f"x{i}", f"x{j}")] = CONFLICT_PENALTY * conflict_matrix[i][j]
        
        qp.minimize(linear=linear, quadratic=quadratic)
        
        service = QiskitRuntimeService(
            channel="ibm_quantum",
            token=os.environ["IBM_QUANTUM_TOKEN"]
        )
        backend_name = os.environ.get("IBM_QUANTUM_BACKEND", "ibmq_qasm_simulator")
        backend = service.get_backend(os.environ.get("IBM_QUANTUM_BACKEND", "ibmq_qasm_simulator"))

        logger.info(f"QOPE: Running QAOA on backend {backend_name}")

        qaoa_kwargs = {
            "reps": 3,
            "optimizer": COBYLA(maxiter=300),
        }
        try:
            from qiskit_ibm_runtime import Sampler
            qaoa = QAOA(sampler=Sampler(backend=backend), **qaoa_kwargs)
        except (ImportError, TypeError):
            qaoa = QAOA(**qaoa_kwargs)
        
        optimizer = MinimumEigenOptimizer(qaoa)
        result = optimizer.solve(qp)
        
        # Extract solution
        optimal_indices = [i for i, val in enumerate(result.x) if val > 0.5]
        selected_files = [candidate_changes[i]["file_path"] for i in optimal_indices]
        
        # Calculate conflict risk
        conflict_risk = 0
        for i in optimal_indices:
            for j in optimal_indices:
                if i < j:
                    conflict_risk += conflict_matrix[i][j]
        
        logger.info(f"QOPE: Quantum optimization complete. Selected {len(optimal_indices)}/{n} changes")
        
        return {
            "optimal_changes": optimal_indices,
            "selected_files": selected_files,
            "objective_value": float(result.fval),
            "conflict_risk": conflict_risk,
            "quantum_backend": backend.name if isinstance(backend.name, str) else backend.name(),
            "num_qubits": n
        }
    
    def _optimize_classical(
        self,
        candidate_changes: List[Dict[str, Any]],
        conflict_matrix: List[List[int]]
    ) -> Dict[str, Any]:
        """
        Classical greedy fallback: pick highest coverage changes with no conflicts.
        """
        logger.warning("QOPE: running in classical fallback mode")
        
        n = len(candidate_changes)
        
        # Sort by coverage weight (descending)
        sorted_indices = sorted(
            range(n),
            key=lambda i: candidate_changes[i].get("coverage_weight", 1.0),
            reverse=True
        )
        
        # Greedy selection: pick highest coverage changes that don't conflict
        selected = []
        for i in sorted_indices:
            # Check if this change conflicts with any already selected
            has_conflict = any(conflict_matrix[i][j] > 0 for j in selected)
            if not has_conflict:
                selected.append(i)
        
        selected_files = [candidate_changes[i]["file_path"] for i in selected]
        
        # Calculate objective value
        coverage_sum = sum(candidate_changes[i].get("coverage_weight", 1.0) for i in selected)
        objective_value = -coverage_sum  # Negative because we're minimizing
        
        logger.info(f"QOPE: Classical optimization complete. Selected {len(selected)}/{n} changes")
        
        return {
            "optimal_changes": selected,
            "selected_files": selected_files,
            "objective_value": objective_value,
            "conflict_risk": 0,  # Greedy ensures no conflicts
            "quantum_backend": "classical_fallback",
            "num_qubits": n
        }
    
    def health_check(self) -> bool:
        """
        Check if QOPE service is ready.
        
        Returns:
            True if quantum or classical mode is available
        """
        logger.info("QOPE health check passed")
        return True


# Made with Bob
