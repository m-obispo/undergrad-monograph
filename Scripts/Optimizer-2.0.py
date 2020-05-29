import numpy as np
from scipy.optimize import minimize
import os
import sys
import time
#Bibliotecas gráficas
#import matplotlib.pyplot as plt
#from mpl_toolkits.mplot3d import Axes3D

#Abre o arquivo .log do programa de otimização
log = open('../Optimizer-log.txt','w')

def minimo(arr):
    '''Retorna o valor mínimo de um array e sua posição'''
    return (np.amin(arr), np.where(arr == np.amin(arr)))

def cabecalho(r, np, fu, b, omega=0.0):
    '''Imprime o cabeçalho de uma entrada do Gaussian'''
    if omega >= 0.0 and omega < 1.0:
        omegaFormat = '0'+str(int(omega*10**9))
        omegaFormat = omegaFormat[:5]+'00000'
        print("omega = ",omega)
        return "%mem="+r+"GB\n%nproc="+np+"\n#p "+fu+"/"+b \
               +" iop(3/107="+omegaFormat+") iop(3/108="+omegaFormat+")" \
               +" int=ultrafine counterpoise=2 Scan\n\nTCC\n\n0 1\n"
    elif omega >= 0.0 and omega > 1.0:
        omegaFormat = str(int(omega*10**10))
        omegaFormat = omegaFormat[:5]+'00000'
        print("omega = ",omega)
        return "%mem="+r+"GB\n%nproc="+np+"\n#p "+fu+"/"+b \
               +" iop(3/107="+omegaFormat+") iop(3/108="+omegaFormat+")" \
               +" int=ultrafine counterpoise=2 Scan\n\nTCC\n\n0 1\n"
    else:
        return "%mem="+r+"GB\n%nproc="+np+"\n#p "+fu+"/"+b \
               +" int=ultrafine counterpoise=2 Scan\n\nTCC\n\n0 1\n"
#

funct = sys.argv[1]
base = 'aug-cc-PVTz'

log.write("Funcional: "+funct+
        "\nBase: "+basis)

M = 36 #No. de pontos das curvas angulares
N = 21 #No. de pontos das curvas radiais

print('Gerando Entradas...')
log.write('Gerando Entradas...')
def geraEntrada(omega=0.0):
    '''Gera as entradas para o Gaussian com o valor de ômega dado'''
    ram = '8'
    nproc = '8'
    #Distâncias (em angstroms) e ângulos (em graus) da geometria do sistema H2O2-Kr
    D = 1.450             #Distância O-O
    d = 0.966             #Distância O-H
    chi = 108.0*np.pi/180 #Ângulo O-O-H
    teta1 = 0.0           #Ângulo entre uma das ligações O-H e o eixo y
    teta2 = 0.0           #Ângulo entre uma das ligaçẽos O-H e o eixo y
    dTeta = 10.*np.pi/180 #Passo da variação de teta1 e teta2
    R = 8.0               #Distância entre O-O e Kr

    atom = ['O','O','H','H','Kr']
    x = [0.0, 0.0, 0.0, 0.0, 0.0]
    y = [0.0, 0.0, d*np.sin(chi)*np.cos(teta1), d*np.sin(chi)*np.cos(teta2), R]
    z = [D/2, -D/2, D/2 - d*np.cos(chi), - D/2 + d*np.cos(chi), 0.0]

    for t in [0,17]: #range(M):
        x = [0.0, 0.0, d*np.sin(chi)*np.sin(teta1+dTeta*t), d*np.sin(chi)*np.sin(teta2), 0.0]
        y = [0.0, 0.0, d*np.sin(chi)*np.cos(teta1+dTeta*t), d*np.sin(chi)*np.cos(teta2), 0.0]#R-t*dR
        z = [D/2, -D/2, D/2 - d*np.cos(chi), - D/2 + d*np.cos(chi), 0.0]
        with open('../Inputs/Inputs-'+funct+'/H2O2-Kr_'+str(t)+'.com','w') as h:
            h.write(cabecalho(ram,nproc,funct,base,omega))
            print(t)
            for j in range(len(atom)-1):
                h.write(atom[j]+"(Fragment=1)   "+str(x[j])+"  "+str(y[j])+"  "+str(z[j])+"\n")
            h.write('Kr(Fragment=2)   0.    R1    0.')
            h.write('\n Variables:\n R1 3.0 S 20 +0.1\n')
            h.write("\n")


MP4 = np.zeros(21)
#Lê os logs com os dados da SEP de referência (MP4)
print('Lendo energias de referência (MP4)...')
log.write('Lendo energias de referência (MP4)...')
for k in [0,17]: #range(M):
    R = np.arange(3,5.1,0.1)
    mp4 = []
    keywords = ['Counterpoise', 'corrected', 'energy']
    with open('../Logs/Logs/H2O2-Kr_'+str(k)+'.log','r') as g:
        for line in g:
            linha = line.split()
            #print(linha)
            if linha[:3] == keywords:
                # print(linha, linha[-1])
                mp4.append(float(linha[-1]))
                # print('Energia '+str(k)+':',float(linha[-1]/219474.6305))
                log.write('Arquivo '+g.name+' lido com sucesso!'+
                        '\nEnergia '+str(k)+':',float(linha[-1]/219474.6305))

    MP4 = np.vstack((MP4,np.array(mp4)))

MP4 = MP4[1:,:]
print('Sucesso!')

print('Declarando parâmetros da otimização...')
log.write('Declarando parâmetros da otimização...')
vetorUnit = np.repeat(1.,N)
pesoInicial = np.array([1.0*vetorUnit, 2.0*vetorUnit])
# pesoAngular = np.append(np.repeat(0.5, 10), np.append(np.repeat(1.0, 16), np.repeat(0.5, 10)))
# pesoTotal = np.array([x*vetorUnit for x in pesoTotal]) 
count = 0 #Conta o número de iterações do Gaussian

def SEP(omega, peso = np.repeat(1.0, N)):

    '''Lê os logs com os dados da SEP a ser otimizada (DFT)
    e realiza o cálculo da diferença entre esta e a SEP de referência'''

    global R, DFT, MP4, dE, MSE   
    #Valor dos pesos do erro médio quadrático para cada coordenada angular
    SCF = np.zeros(21)
    log.write('Iteração no. '+str(count)+' iniciada')

    geraEntrada(omega)      #Gera as entradas a serem utilizadas pelo Gaussian.
    t0 = time.time()
    os.system('bash roda-um.sh '+funct)  #Executa os cálculos do Gaussian, um por vez.
    print('Tempo de execução do Gaussian (s): ', time.time()-t0)

    log.write('Iteração no. '+str(count)+' finalizada!'+
            '\nTempo de execução do Gaussian (s): '+str(time.time()-t0))

    for k in [0,17]: #range(M):
        R = np.arange(3,5.1,0.1)
        scf = []
        keywords = ['Counterpoise:', 'corrected', 'energy']
        with open('../Logs/Logs-'+funct+'/H2O2-Kr_'+str(k)+'.log','r') as g:
            for line in g:
                linha = line.split()
                if linha[:3] == keywords:
               	    scf.append(float(linha[-1]))
                    # print('Energia '+str(k)+':',float(linha[-1]/219474.6305))
                    log.write('Arquivo '+g.name+' lido com sucesso!'+
                            '\nEnergia '+str(k)+':',float(linha[-1]/219474.6305))

        SCF = np.vstack((SCF,np.array(scf)))
        #print(SCF)

    DFT = SCF[1:,:]
    MSE = (MP4 - DFT)
    #print(DFT)
    dE = np.abs(MP4 - DFT)
    dE2 = dE*dE
    MSE = (dE2*peso).mean()

    print('Erro máximo: ', np.amax(dE))
    print('Menores energias: ',minimo(MP4), minimo(DFT))
    print("Erro médio quadrático: ", MSE)

    log.write('Erro máximo: {}'.format(np.amax(dE)))
    log.write('Menores energias: {}, {}'.format(minimo(MP4), minimo(DFT)))
    log.write("Erro médio quadrático: {}".format(MSE))

    return MSE

#Definindo rotina de otimização
print('Iniciando otimização...')
ti = time.time()
# resultado = minimize(SEP, np.append(0.25, pesoInicial), method="BFGS", options = {'disp':True, 'eps':1e-3})
resultado = minimize(SEP, 0.25, args = pesoInicial, method="Nelder-Mead", options = {'disp':True,'fatol': 1e-7})
tf = time.time() - ti

wOpt = resultado['x']# = 0.25 para wb97xd
                     # = 1.35 para lc-blyp
		             # = 0.55 para lc-wpbe

tfh = int(tf/60/60)
tfm = int((tf/60/60 - int(tf/60/60))*60)
str_TF = str(tfh)+'h'+str(tfm)+'min'

print('---RESULTADOS FINAIS---')
print('-----------------------')
print(resultado)
print('Tempo total de execução da otimização: ',str_TF)
print('-----------------------')

with open('../resultado_'+funct+'.txt', 'w') as h:
    h.write('----------------RESULTADOS FINAIS--------------\n')
    h.write('Tempo total de execução da otimização: '+str_TF+'\n\n')
    for i in resultado:
        h.write(str(i)+": "+str(resultado[i])+"\n")
    for i in range(len(DFT[:,0])):
        h.write('\n----------------- TETA = '+str(float(i*10))+' ------------------\n')
        h.write('\n R - ------- DFT -------- ------- MP4 ---------\n')
        for j in range(len(R)):
            #print(i,j)
            #h.write(str(R[j])+"       "+str(DFT[i,j])+"       "+str(MP4[i,j])+"\n")
            h.write("%0.9f   %0.9f   %0.9f\n"%(R[j], DFT[i,j], MP4[i,j]))
    h.write('-----------------------------------------------\n')

log.write('----------------RESULTADOS FINAIS--------------\n')
log.write('Tempo total de execução da otimização: '+str_TF+'\n\n')
for i in resultado:
    log.write(str(i)+": "+str(resultado[i])+"\n")
for i in range(len(DFT[:,0])):
    log.write('\n----------------- TETA = '+str(float(i*10))+' ------------------\n')
    log.write('\n R - ------- DFT -------- ------- MP4 ---------\n')
    for j in range(len(R)):
        #print(i,j)
        #h.write(str(R[j])+"       "+str(DFT[i,j])+"       "+str(MP4[i,j])+"\n")
        log.write("%0.9f   %0.9f   %0.9f\n"%(R[j], DFT[i,j], MP4[i,j]))
log.write('-----------------------------------------------\n')

#Plot 3D
#Teta = np.arange(0,360,10)
#r,teta = np.meshgrid(R,Teta)

# ax1 = plt.subplot(111, projection='3d')
# ax1.set_title('Superfície de Energia Potencial (Comparativo)')
# ax1.plot_surface(r,teta,DFT,cmap='twilight_r',rcount = 100,ccount=100, label = 'Diferença')
# ax1.set_xlabel('R $(\\mathring{A})$')
# ax1.set_ylabel('$\\theta$ $(^o)$')
# ax1.set_zlabel('Energia $(cm^{-1})$')
# plt.show()

#Plot 2D

# #plt.suptitle("Curvas de Energia Potencial", fontsize = '22')
# fig, [graf1, graf2] = plt.subplots(1,2)
# graf3 = graf1.twinx()
# graf4 = graf2.twinx()
#
# graf1.set_title("Ângulo diédrico: $ \\theta = 100 ^o$", fontsize = '20')
# graf1.grid()
# graf1.set_xlabel('$R (\\mathring{A})$', fontsize = '18')
# graf1.set_ylabel('Energia $(cm^{-1})$', fontsize = '18')
# graf3.set_ylabel('Energia $(cm^{-1})$', fontsize = '18')
# graf1.set_ylim()
# graf1.plot(R, MP4, 'k', label = 'MP4')
# graf3.plot(R, DFT, 'g', label = 'DFT')
# graf1.legend()
# graf3.legend()
#
# graf2.set_title("Distância $\\mathrm{H_2O_2 - Kr}: R  = 3,5\\, \\mathring{A}$", fontsize = '20')
# graf2.grid()
# graf2.legend(fontsize = '18')
# graf2.set_xlabel('$\\theta (^o)$', fontsize = '18')
# graf2.set_ylabel('Energia $(cm^{-1})$', fontsize = '18')
# graf4.set_ylabel('Energia $(cm^{-1})$', fontsize = '18')
# graf2.plot(Teta, dE[:,5], 'k', label = 'MP4')
# #graf4.plot(Teta, DFT[:,5], 'r', label = 'DFT')
# graf2.legend(fontsize = '18')
# graf4.legend(fontsize = '18')
#
# plt.show()

log.close()

#       wb97xd
#      fun: 7.950941737661435e-06
# hess_inv: array([[81067.657761]])
#      jac: array([0.])
#  message: 'Optimization terminated successfully.'
#     nfev: 33
#      nit: 3
#     njev: 11
#   status: 0
#  success: True
#        x: array([0.25111888])
