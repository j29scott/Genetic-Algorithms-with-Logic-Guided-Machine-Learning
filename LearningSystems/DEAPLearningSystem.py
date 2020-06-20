from inspect import signature
import operator
import traceback
import warnings
warnings.filterwarnings("ignore")


from LearningSystems.LearningSystem import LearningSystem
from Customization import *
from Constraints import *

from deap import base
from deap import creator
from deap import tools
from deap import algorithms
from deap import gp
import numpy as np

class DEAPLearningSystem(LearningSystem):
    """
    Learning Algorithm that implements the DEAP Python Library
    """
    def __init__(self, path="DEAP_data", verbose=False, population_size=100, crossover_prob=0.4, mutation_prob=0.4, ngens=30, algorithm="simple", func_list=['add', 'mul', 'sub', 'div', 'sin', 'cos', 'tan', 'exp', 'sqrt']):
        """
        Parameters
        -----------
        path : str
            Location to save graphs and data

        verbose : boolean
            True iff you want to see verbose fit for DEAP

        population_size : int
            The number of equations we want to generate every generation

        crossover_prob : float
            Probability that we crossover two equations randomly

        mutation_prob : float
            Probability that we mutate an equation randomly

        ngens : int
            Number of generations we wish to train for

        algorithm: string
            Algorithm to use for training. Current options
            simple: eaSimple
            mu+lambda: eaMuPlusLambda
            mu,lambda: eaMuCommaLambda

        func_set : list
            List of strings i.e names of functions to include / operations to consider
            Check Customizations for full list

        """
        LearningSystem.__init__(self)
        self.toolbox = base.Toolbox()
        self.path = path
        self.verbose = verbose
        self.population_size=population_size
        self.crossover_prob = crossover_prob
        self.mutation_prob = mutation_prob
        self.ngens = ngens
        self.algorithm = algorithm
        self.func_list = func_list
        self.add_func = lambda dls, x, y : 0 # Zero Function Default
        self.creator = creator

    def create_fitness(self):
        """
        Creates a Fitness function and registers it with the toolbox as DEAP library requires
        Assumes self.toolbox is defined

        Currently minimizes a single objective function
        """
        self.creator.create("Fitness", base.Fitness, weights=(-1.0,))
        self.Fitness = self.creator.Fitness
        return

    def create_and_reg_individual(self, problem_arity):
        """
        Creates an individual and registers it with the toolbox as DEAP library requires. 
        Assumes self.create_fitness() has been called

        Currently creates an individual that inherits from PrimitiveTree and uses the primitives mentioned in list just as the default DEAP examples

        Parameters
        -----------
        problem_arity : int
            The number of input variables for this symbolic regression problem
        """

        self.pset = gp.PrimitiveSet("MAIN", arity=problem_arity)
        for func in self.func_list:
            self.pset.addPrimitive(func_dict[func], len(signature(func_dict[func]).parameters), name=func)

        self.creator.create("Individual", gp.PrimitiveTree, fitness=self.Fitness,
                       pset=self.pset)
        self.toolbox.register("expr", gp.genHalfAndHalf, pset=self.pset, min_=1, max_=2)
        self.toolbox.register("individual", tools.initIterate, self.creator.Individual,
                         self.toolbox.expr)
        return

    def create_and_reg_population(self):
        """

        Currently uses bad model
        """
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)
        return

    def reg_selection(self, tournsize):
        """
        Registers our method of selection.

        Parameters
        -----------
        tournsize : int
            How many equations to select for every gen
        """
        self.toolbox.register("select", tools.selTournament, tournsize=tournsize)
        return

    def reg_mutation(self):
        """
        Controls how equations mutate
        """
        self.toolbox.register("expr_mut", gp.genFull, min_=0, max_=2)
        self.toolbox.register("mutate", gp.mutUniform, expr=self.toolbox.expr_mut, pset=self.pset)
        self.toolbox.decorate("mutate", gp.staticLimit(key=operator.attrgetter("height"), max_value=17))
        return
       
    def reg_mating(self):
        """
        Controls how e cross species
        """
        self.toolbox.register("mate", gp.cxOnePoint)
        self.toolbox.decorate("mate", gp.staticLimit(key=operator.attrgetter("height"), max_value=17))
        return

    def eval_helper(self, ind, X, y):
        """
        Given an X and a y returns the mse + addfunc of a given ind
        """
        self.func = gp.compile(ind, self.pset)
        mse = self._mse(self.func, X, y)
        a = self.add_func(self, X, y) 
        return (mse + a,)

    def reg_eval(self, X, y):
        """
        registered the evaluation method we wanna use in this function

        Currently uses mean squared error but this is what we will have to or want to change to bring in LGML
        
        Parameters
        ------------
        X, y - Data columns and target series
        """
        self.toolbox.register('evaluate', self.eval_helper, X=X , y=y)
        return

    def reg_gen_eval(self, generator):
        """
        registered the evaluation method using a generator

        Parameters
        --------------
        generator - a function which when called returns an X, y 
        """
        def eval(ind, gen):
            X, y = gen()
            return self.eval_helper(ind, X, y)
        self.toolbox.register('evaluate', eval, gen=generator)

    def get_result(self, func, X, y):
        """
        Returns a series that holds all the values func(X)
        """
        def temp(row):
                try:
                    val = func(*row)
                    #print(f"Value {val} was succesfully calculated for {str(expr)}")
                    return val
                except:
                    traceback.print_exc()
                    return 9999
        X['result'] = X.copy().apply(lambda row: temp(row), axis=1)
        to_return = X['result'].copy()
        X.drop('result', axis=1, inplace=True)
        return to_return

    def _mse(self, func, X, y):
        """
        Returns the mean square error of a function which can compute the value of f(X)
        """
        preds = self.get_result(func, X, y)
        diff = preds - y
        return np.mean(diff**2)

    def ind_score(self, ind, X, y):
        """
        Method to score and indivudual

        Currently uses mean squared error, violations
        
        Parameters
        ------------
        X, y - Data columns and target series
        """
        self.func = gp.compile(ind, self.pset)
        mse = self._mse(self.func, X, y)
        violation = self.add_func(self, X, y)
        return (mse, violation)

    def get_arity_from_X(self, X):
        return len(X.columns)
    #########################################################################
    
    def set_add_func(self, func):
        """
        Set additional process.
        
        Parameters
        ---------------
        fun : function(deaplearningsystemobject dls, X, y) -> float
            Remember 
                you can use dls.func to get the function to get the functional transformation
                you can use dls.get_result to get the preds in a series
        """
        self.add_func = func

    def set_algorithm(self, algorithm):
        self.algorithm = algorithm

    def reset(self):
        """
        Clears all working data so it was as if this object was a newly created DEAPLearnSystem immediately after initialization
        """
        self.toolbox = base.Toolbox()
        try:
            del self.Fitness
            del self.pset
            del self.hof
        except:
            print("Already Reset")
        return

    def build_model(self, X, y, tournsize=3):
        """
        Runs the builder functions in order with data
        """
        arity = self.get_arity_from_X(X)
        self.invariant_build_model(arity, tournsize)
        self.reg_eval(X, y)
        return

    def build_gen_model(self, generator, tournsize=3):
        """
        Runs builder functions in order with generator
        """
        smallx, smally = generator(no_samples=1)
        arity = self.get_arity_from_X(smallx)
        self.invariant_build_model(arity, tournsize)
        self.reg_gen_eval(generator)

    def invariant_build_model(self, arity, tournsize):
        self.create_fitness()
        self.create_and_reg_individual(arity)
        self.create_and_reg_population()
        self.reg_selection(tournsize)
        self.reg_mutation()
        self.reg_mating()

    def set_func_list(self, func_list):
        """
        Parameters
        -----------
        func_set : list
            Refer to Customization.py for list of functions
        """
        self.func_list = func_list
        return

    def __str__(self):
        return "DEAP"

    def train(self):
        """
        Assumes that model is fully built

        Currently uses a simple algorithm and returns the hall of famer
        Clears the existing trained model every time fit is called
        """
        self.hof = tools.HallOfFame(1)
        pop, log = Algorithms.get_algorithm(self.algorithm)(population=self.toolbox.population(self.population_size), toolbox=self.toolbox, cxpb=self.crossover_prob, mutpb=self.mutation_prob, ngen=self.ngens, halloffame=self.hof, verbose=self.verbose)
        return pop, log

    def fit(self, X, y):
        """
        Fit using fixed X and y
        """
        self.reset()
        self.build_model(X, y)
        return self.train()

    def fit_gen(self, gen):
        """
        Fit using generator
        """
        self.reset()
        self.build_gen_model(gen)
        return self.train()

    def get_predicted_equation(self):
        return self.toolbox.clone(self.hof[0])

    def score(self, X, y):
        """
        Returns the evaluation on this model as per its mse
        """
        try:
            best = self.hof[0]
            return self.ind_score(best, X, y)
        except:
            print(f"Could not find Best model")
            return 0



class Algorithms():
    """
    Class to hold all of the Algorithms used for DEAPLearningSystem
    All hyperparameters than are unique to a particular function are defined here.
        Not defined here - pop, toolbox, cxpb, mutpb, ngen
    """
    mu = 5
    lambda_ = 8

    algo_dict = {
        "simple" : algorithms.eaSimple,
        "mu+lambda" : lambda population, toolbox, cxpb, mutpb, ngen,  halloffame, verbose : algorithms.eaMuPlusLambda(population=population, toolbox=toolbox, mu=Algorithms.mu, lambda_=Algorithms.lambda_, cxpb=cxpb, mutpb=mutpb, ngen=ngen, halloffame=halloffame, verbose=verbose),
        "mu,lambda" : lambda population, toolbox, cxpb, mutpb, ngen,  halloffame, verbose : algorithms.eaMuCommaLambda(population=population, toolbox=toolbox, mu=Algorithms.mu, lambda_=Algorithms.lambda_, cxpb=cxpb, mutpb=mutpb, ngen=ngen, halloffame=halloffame, verbose=verbose),

        }

    def get_algorithm(key):
        """
        Returns the algorithm function associated with the key
        Defaults to eaSimple if key not found
        """
        if key not in Algorithms.algo_dict.keys():
            print(f"Key {key} not found out of available algorithm options. Using Simple Algorithm")
            algorithms.ea
        return Algorithms.algo_dict.get(key, Algorithms.algo_dict.get("simple"))

    def basic_self(population, toolbox, cxpb, mutpb, ngen, halloffame, verbose):
        """

        """
        pass



    

