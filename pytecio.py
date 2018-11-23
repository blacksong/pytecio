import ctypes
import numpy as np
import sys
from pathlib import Path
import os
def get_dll():
    if sys.platform.startswith('win'):
        p = Path(os.environ['HOMEDRIVE']) / os.environ['HOMEPATH'] / '.yxspkg'/'pytecio'
        if not p.is_dir():
            os.makedirs(p)
        dll_path = p / 'tecio.dll'
        if not dll_path.is_file():
            from urllib import request
            url = 'https://raw.githubusercontent.com/blacksong/pytecio/master/2017r3_tecio.dll'
            print('Downloading dll from github:',url)
            request.urlretrieve(url,dll_path)
        return ctypes.cdll.LoadLibrary(str(dll_path))
    elif sys.platform.startswith('linux'):
        p = Path(os.environ['HOME']) / '.yxspkg'/'pytecio'
        if not p.is_dir():
            os.makedirs(p)
        dll_path = p / 'tecio.so'
        if not dll_path.is_file():
            from urllib import request
            url = 'https://raw.githubusercontent.com/blacksong/pytecio/master/2017r3_tecio.so'
            print('Downloading dll from github:',url)
            request.urlretrieve(url,dll_path)
        return ctypes.cdll.LoadLibrary(str(dll_path))
GLOBAL_DLL = get_dll()        
class zone_data(dict):
    def __init__(self,parent,zone_n):
        super().__init__()
        self.parent = parent
        self.zone_n = zone_n 
        self.update({i:None for i in parent.nameVars})
    def __getitem__(self,key):
        if isinstance(key, int):
            key = self.parent.nameVars[key]
        t = super().__getitem__(key)
        if t is None:
            var_n = self.parent.nameVars_dict[key] + 1
            t = self.parent._read_zone_var(self.zone_n, var_n)
            self[key] = t
            return t
        else:
            return t
    def __setitem__(self,key,value):
        if isinstance(key, int):
            key = self.parent.nameVars[key]
        if key not in self.parent.nameVars:
            self.parent._add_variable(self.zone_n,key,value)
        super().__setitem__(key,value)
    def __getattr__(self,attr):
        if attr == 'Elements':
            self.Elements = self.parent._retrieve_zone_node_map(self.zone_n)
            return self.Elements
        else:
            raise Exception('no attribute {}'.format(attr))
#zone_n:the number of zones, start from 1 to end, var_n is the same

#经测试Double类型的数据FieldDataType_Double的值为2
FieldDataType_Double = 2
FieldDataType_Float  = 1

FieldDataType_Int32 = -100 # -100:not defined
FieldDataType_Int16 = -100 
FieldDataType_Byte = -100

class read_tecio(dict):

    def __init__(self,filename):
        super().__init__()
        self.dll = GLOBAL_DLL
        self.filename = filename
        self.filehandle = self._get_filehandle()
        self.title = self._tecDataSetGetTitle()
        self.numVars = self._tecDataSetGetNumVars()
        self.nameVars = self._tecVarGetName()

        self.fileType = self._tecFileGetType()
        self.numZones = self._tecDataSetGetNumZones()
        self.nameZones = self._tecZoneGetTitle()

        self.nameZones_dict = {k:i for i,k in enumerate(self.nameZones)}
        self.nameVars_dict = {k:i for i,k in enumerate(self.nameVars)}
        
        def cal_zone(i,zone_name):
            d = dict()
            d['varTypes'] = [self._tecZoneVarGetType(i+1,j+1) for j in range(self.numVars)]
            d['passiveVarList'] = [self._tecZoneVarIsPassive(i+1,j+1) for j in range(self.numVars)]
            d['shareVarFromZone'] = [self._tecZoneVarGetSharedZone(i+1,j+1) for j in range(self.numVars)]
            # valueLocation: value 1 represent the data is saved on nodes, value 0 means on elements center
            d['valueLocation'] = [self._tecZoneVarGetValueLocation(i+1,j+1) for j in range(self.numVars)]
            d['IJK'] = self._tecZoneGetIJK(i+1)
            d['zoneType'] = self._tecZoneGetType(i+1)
            d['solutionTime'] = self._tecZoneGetSolutionTime(i+1)
            d['strandID'] = self._tecZoneGetStrandID(i+1)
            d['shareConnectivityFromZone'] = self._tecZoneConnectivityGetSharedZone(i+1)
            d['faceNeighborMode'] = self._tecZoneFaceNbrGetMode(i+1)
            d['numFaceConnections'] = self._tecZoneFaceNbrGetNumConnections(i+1)
            d['parentZone'] = self._tecZoneGetParentZone(i+1)
            d['name'] = zone_name
            return d
        self.zone_info = [cal_zone(i,zone_name) for i,zone_name in enumerate(self.nameZones)]
        self.update({name:zone_data(self,i+1) for i,name in enumerate(self.nameZones)})
        # self._retrieve_zone_node_map(1)
        self._retrieve_aux_data(1)

    def __getitem__(self,key):
        if isinstance(key, int):
            key = self.nameZones[key]
        return super().__getitem__(key)
    def _read_zone_var(self,zone_n,var_n):
        
        info = self.zone_info[zone_n - 1]
        numValues = self._tecZoneVarGetNumValues(zone_n, var_n)

        if info['passiveVarList'][var_n - 1] is 0:
            fieldDataType = info['varTypes'][var_n-1]
            if fieldDataType is FieldDataType_Float:
                d = self._get_data_all_type(zone_n, var_n, numValues, ctypes.c_float, self.dll.tecZoneVarGetFloatValues)
                np_array = np.array(d)
            elif fieldDataType is FieldDataType_Double:
                d = self._get_data_all_type(zone_n, var_n, numValues, ctypes.c_double, self.dll.tecZoneVarGetDoubleValues)
                np_array = np.array(d)
            else:
                raise Exception('FieldDataType Error:not defined data type')
            return np_array
        else:
            return np.array([])
    def _get_data_all_type(self, zone_n, var_n, numValues, c_type, fun):
        t = (c_type*numValues)()
        fun(self.filehandle, zone_n, var_n, 1, numValues, t)
        return t
    def _get_filehandle(self):
        '''get the filehandle'''
        p = ctypes.c_int(13)
        p1 = ctypes.pointer(p)
        filehandle = ctypes.pointer(p1)
        name = ctypes.c_char_p(self.filename.encode())
        self.dll.tecFileReaderOpen(name,filehandle)
        return filehandle[0]
    def _tecDataSetGetTitle(self):
        '''get the title of data set'''
        s = ctypes.c_char_p()
        ll = ctypes.pointer(s)
        self.dll.tecDataSetGetTitle(self.filehandle,ll)
        t = ll[0].decode()

        return t
    def _tecDataSetGetNumVars(self):
        t = ctypes.c_int(0)
        p = ctypes.pointer(t)
        self.dll.tecDataSetGetNumVars(self.filehandle,p)
        return p[0]
    def _tecVarGetName(self):
        def get_name(i):
            s = ctypes.c_char_p()
            ll = ctypes.pointer(s)
            self.dll.tecVarGetName(self.filehandle,i,ll)
            return ll[0].decode()
        name_list = [get_name(i) for i in range(1,self.numVars+1)]

        return name_list
    def _tecFileGetType(self):
        '''获取文件类型，即数据存储的格式在写文件的时候可以用到'''
        s = ctypes.c_int(-100)
        ll = ctypes.pointer(s)
        self.dll.tecFileGetType(self.filehandle,ll)
        t = ll[0]

        return t
    def _tecDataSetGetNumZones(self):
        '''获取数据总共包含的zone的个数'''
        t = ctypes.c_int(0)
        p = ctypes.pointer(t)
        self.dll.tecDataSetGetNumZones(self.filehandle,p)

        return p[0]
    def _tecZoneGetTitle(self):
        '''获取每个zone的名字'''
        def get_name(i):
            s = ctypes.c_char_p()
            ll = ctypes.pointer(s)
            self.dll.tecZoneGetTitle(self.filehandle,i,ll)
            return ll[0].decode()
        name_list = [get_name(i) for i in range(1,self.numZones+1)]

        return name_list
    def _tecZoneVarGetType(self,zone_n,var_n):
        '''获取数据存储的类型 是double（64） 还是single（32）double型返回True'''
        p = self._return_2_int(zone_n,var_n,self.dll.tecZoneVarGetType)
        #if p is FieldDataType_Double, it is double format
        return p
        
    def _tecZoneVarGetSharedZone(self,zone_n,var_n):
        '''    '''
        return self._return_2_int(zone_n,var_n,self.dll.tecZoneVarGetSharedZone)
    
    def _tecZoneVarGetValueLocation(self,zone_n,var_n):
        '''    '''
        return self._return_2_int(zone_n,var_n,self.dll.tecZoneVarGetValueLocation)
    
    def _tecZoneVarIsPassive(self,zone_n,var_n):
        '''    '''
        return self._return_2_int(zone_n, var_n, self.dll.tecZoneVarIsPassive)
    
    def _return_1_int(self,n,fun):
        '''执行fun(filehandle,int,&int)函数并返回结果'''
        p = ctypes.pointer(ctypes.c_int(0))
        fun(self.filehandle,n,p)
        return p[0]

    def _add_variable(self,zone_n,var_name,value):
        ''' add a new variable to all zones'''
        info = self.zone_info[zone_n -1]
        self.nameVars.append(var_name)
        self.nameVars_dict[var_name] = len(self.nameVars) - 1
        info['varTypes'].append(info['varTypes'][-1])
        info['shareVarFromZone'].append(0)
        I,J,K = info['IJK']
        if info['zoneType'] is 0:#IJK type
            if value.size == I*J*K:
                valueLocation = 1
            else:
                valueLocation = 0
        else:
            if value.size == I:
                valueLocation = 1
            else:
                valueLocation = 0
        info['valueLocation'].append(valueLocation)
        info['passiveVarList'].append(0)
        for zone_p, item in enumerate(self.zone_info):

            if zone_n == zone_p+1:
                continue
            else:
                item['varTypes'].append(item['varTypes'][-1])
                item['shareVarFromZone'].append(0)
                item['valueLocation'].append(valueLocation)
                item['passiveVarList'].append(1)
        for zone_data_ in self.values():
            zone_data_[var_name] = None
    def _return_2_int(self,zone_n,var_n,fun):
        '''执行fun(filehandle,int,int,&int)函数并返回结果'''
        p = ctypes.pointer(ctypes.c_int(0))
        fun(self.filehandle,zone_n,var_n,p)
        return p[0]
    def _return_n_array(self,fun,c_type, numValues,*d):
        '''输入参数是n个整数，返回长为numValues的c_type类型的一个数组并转化为ndarry'''
        t = (c_type*numValues)()
        fun(self.filehandle, *d, t)
        return np.array(t)
    def _tecZoneGetType(self,zone_n):
        '''获取zone的类型'''
        t = self._return_1_int(zone_n,self.dll.tecZoneGetType)
        if t is 6 or t is 7:
            raise Exception('Unsupported zone type')

        return t
    
    def _tecZoneGetIJK(self,zone_n):
        '''获取该zone 的ijk的值'''
        iMax = ctypes.pointer(ctypes.c_int(0))
        jMax = ctypes.pointer(ctypes.c_int(0))
        kMax = ctypes.pointer(ctypes.c_int(0))
        self.dll.tecZoneGetIJK(self.filehandle,zone_n,iMax,jMax,kMax)
        t = iMax[0], jMax[0], kMax[0]
 
        return t
    def _tecZoneConnectivityGetSharedZone(self,zone_n):
        shareConnectivityFromZone = self._return_1_int(zone_n,self.dll.tecZoneConnectivityGetSharedZone)
        return shareConnectivityFromZone

    def _tecZoneFaceNbrGetMode(self,zone_n):
        faceNeighborMode = self._return_1_int(zone_n,self.dll.tecZoneFaceNbrGetMode)
        return faceNeighborMode

    def _tecZoneFaceNbrGetNumConnections(self,zone_n):
        numFaceConnections = self._return_1_int(zone_n,self.dll.tecZoneFaceNbrGetNumConnections)
        if numFaceConnections>0:
            raise Exception('numFaceConnections>0: maybe something wrong with this program')
        return numFaceConnections

    def _tecZoneGetSolutionTime(self,zone_n):
        d = ctypes.c_double(0.0)
        p = ctypes.pointer(d)
        self.dll.tecZoneGetSolutionTime(self.filehandle,zone_n,p)
        solutionTime = p[0]

        return solutionTime

    def _tecZoneGetStrandID(self,zone_n):
        StrandID = self._return_1_int(zone_n,self.dll.tecZoneGetStrandID)

        return StrandID

    def _tecZoneGetParentZone(self,zone_n):
        parentZone = self._return_1_int(zone_n,self.dll.tecZoneGetParentZone)

        return parentZone

    def _tecZoneVarGetNumValues(self,zone_n,var_n):
        numValues = self._return_2_int(zone_n,var_n,self.dll.tecZoneVarGetNumValues)

        return numValues

    def _tecZoneFaceNbrGetNumValues(self,zone_n):
        k = self._return_1_int(zone_n,self.dll.tecZoneFaceNbrGetNumValues)

        return k
    def _retrieve_zone_node_map(self,zone_n):
        info = self.zone_info[zone_n-1]
        if info['zoneType'] is not 0 and info['shareConnectivityFromZone'] is 0:
            jMax = info['IJK'][1]
            numValues = self._tecZoneNodeMapGetNumValues(zone_n,jMax)

            is64Bit = self._tecZoneNodeMapIs64Bit(zone_n)
            if is64Bit is not 0:
                #is64bit True
                nodeMap = self._return_n_array(self.dll.tecZoneNodeMapGet64, ctypes.c_long, numValues, zone_n,1,jMax)
            else:
                nodeMap = self._return_n_array(self.dll.tecZoneNodeMapGet, ctypes.c_long, numValues, zone_n,1,jMax)

        return nodeMap.reshape((jMax,-1))
    def _retrieve_aux_data(self,zone_n):
        numItems = self._tecZoneAuxDataGetNumItems(zone_n)

        if numItems!=0:
            raise Exception('aux data exists, there is an error')
    def _tecZoneAuxDataGetNumItems(self,zone_n):
        return self._return_1_int(zone_n,self.dll.tecZoneAuxDataGetNumItems)

    def _retrieve_custom_label_sets(self,zone_n):
        pass

    def _tecCustomLabelsGetNumSets(self,zone_n):
        return self._return_1_int(zone_n,self.dll.tecCustomLabelsGetNumSets)

    def _tecZoneNodeMapGetNumValues(self,zone_n,jmax):
        return self._return_2_int(zone_n,jmax,self.dll.tecZoneNodeMapGetNumValues)
    
    def _tecZoneNodeMapIs64Bit(self, zone_n):
        return self._return_1_int(zone_n,self.dll.tecZoneNodeMapIs64Bit)

    def close(self):
        self.dll.tecFileReaderClose(ctypes.pointer(self.filehandle))
    
    def write(self,filename,verbose = True):
        k = write_tecio(filename,self,verbose=verbose)
        k.close()

class write_tecio:
    fileFormat = 0 #.szplt

    def __init__(self,filename,dataset=None ,verbose = True):
        self.filename = filename
        self.verbose = verbose
        self.dataset = dataset
        self.dll = GLOBAL_DLL
        self.filehandle = self._get_filehandle()
        for i,zone_name in enumerate(dataset.nameZones):
            info = dataset.zone_info[i]
            I,J,K = info['IJK']
            varTypes = self._list_to_int_array(info['varTypes'])

            #因为这里有个bug所以我加了这样一句转化,原因是第一个zone共享了第一个zone 在创建的时候会导致失败，所以在写文件时强制取消shared
            shareVarFromZone = self._list_to_int_array(info['shareVarFromZone'])
            valueLocation = self._list_to_int_array(info['valueLocation'])
            passiveVarList = self._list_to_int_array(info['passiveVarList'])

            if info['zoneType'] == 0:
                outputZone = self._tecZoneCreateIJK(zone_name,I,J,K,varTypes, shareVarFromZone,
                valueLocation, passiveVarList, info['shareConnectivityFromZone'], info['numFaceConnections'], info['faceNeighborMode'])
            else:
                outputZone = self._tecZoneCreateFE(zone_name, info['zoneType'], I, J, varTypes, shareVarFromZone,
                valueLocation, passiveVarList, info['shareConnectivityFromZone'], info['numFaceConnections'], info['faceNeighborMode'])
            
            self._tecZoneSetUnsteadyOptions(outputZone, info['solutionTime'], info['strandID'])
            if info['parentZone'] != 0:
                self._tecZoneSetParentZone(outputZone,info['parentZone'])
            zone_set = dataset[zone_name]
            for j,var_name in enumerate(dataset.nameVars):

                var_n = j+1
                data=zone_set[var_name]


                ff = [min(i,j) for j in info['shareVarFromZone']]
                if info['passiveVarList'][var_n - 1] is 0 and ff[var_n -1] is 0:
                    
                    fieldDataType = info['varTypes'][var_n-1]
                    if fieldDataType is FieldDataType_Float:
                        self._write_data_all_type(self.dll.tecZoneVarWriteFloatValues, data.ctypes, outputZone, var_n, 0, data.size)
                    elif fieldDataType is FieldDataType_Double:
                        self._write_data_all_type(self.dll.tecZoneVarWriteDoubleValues, data.ctypes, outputZone, var_n, 0, data.size)

                    else:
                        raise Exception('FieldDataType Error:not defined data type')
            self._write_zone_node_map(outputZone, info, zone_set)
    def _write_zone_node_map(self,zone_n,info, zone_set):
        # info = self.dataset.zone_info[self.dataset.nameZones[zone_n-1]]
        if info['zoneType'] is not 0 and info['shareConnectivityFromZone'] is 0:
            Elements = zone_set.Elements
            numValues = Elements.size
            if Elements.itemsize is 8:
                #is64bit True
                self._write_data_all_type(self.dll.tecZoneNodeMapWrite64, Elements.ctypes, zone_n,0,1,numValues)
            else:
                self._write_data_all_type(self.dll.tecZoneNodeMapWrite32, Elements.ctypes, zone_n,0,1,numValues)

    def _list_to_int_array(self,l):
        t = (ctypes.c_int*len(l))()

        for i,j in enumerate( l):
            t[i] = j
        return t
    def _get_filehandle(self):
        p = ctypes.c_int(13)
        p1 = ctypes.pointer(p)
        filehandle = ctypes.pointer(p1)
        name = ctypes.c_char_p(self.filename.encode())
        fileType = self.dataset.fileType
        name_str = ','.join(self.dataset.nameVars)
        # name_str
        var_list_str = ctypes.c_char_p(name_str.encode())
        title_str = ctypes.c_char_p(self.dataset.title.encode())
        if self.filename.endswith('.szplt'):
            fileFormat = 1
        else:
            raise Exception('file format error')
        self.dll.tecFileWriterOpen(name,title_str,var_list_str,fileFormat,fileType,2,None,filehandle)
        
        #官方例子中有这么一个东西，看名字叫debug 感觉不用也可以,就是在输出szplt文件时输出一些信息
        if self.verbose:
            outputDebugInfo = 1
            self.dll.tecFileSetDiagnosticsLevel(filehandle[0],outputDebugInfo)

        return filehandle[0]

    def _tecZoneCreateIJK(self,zoneTitle, iMax, jMax, kMax, varTypes, shareVarFromZone,
        valueLocation, passiveVarList, shareConnectivityFromZone, numFaceConnections, faceNeighborMode):
        p = ctypes.pointer(ctypes.c_int(0))
        zone_title = ctypes.c_char_p(zoneTitle.encode())
        self.dll.tecZoneCreateIJK(self.filehandle, zone_title, iMax, jMax, kMax, varTypes,shareVarFromZone,
        valueLocation, passiveVarList, shareConnectivityFromZone, numFaceConnections, faceNeighborMode,p)
        return p[0]
    
    def _tecZoneCreateFE(self,zoneTitle, zoneType, iMax, jMax, varTypes,shareVarFromZone,
        valueLocation, passiveVarList, shareConnectivityFromZone, numFaceConnections, faceNeighborMode):
        t = ctypes.c_int(0)
        p = ctypes.pointer(t)
        zone_title = ctypes.c_char_p(zoneTitle.encode())

        self.dll.tecZoneCreateFE(self.filehandle, zone_title, zoneType, iMax, jMax, varTypes,shareVarFromZone,
        valueLocation, passiveVarList, shareConnectivityFromZone, numFaceConnections, faceNeighborMode,p)
        return p[0]

    def _tecZoneSetUnsteadyOptions(self,zone_n, solutionTime=0, StrandID=0):
        if solutionTime !=0 or StrandID != 0:
            solutionTime = ctypes.c_double(solutionTime)
            self.dll.tecZoneSetUnsteadyOptions(self.filehandle,zone_n, solutionTime, StrandID)
    
    def _tecZoneSetParentZone(self,zone_n,zone_parent):
        self.dll.tecZoneSetParentZone(self.filehandle,zone_n,zone_parent)

    def _write_data_all_type(self,fun,data, *d):

        fun(self.filehandle, *d, data)
    def close(self):
        self.dll.tecFileWriterClose(ctypes.pointer(self.filehandle))
def read(filename):
    return read_tecio(filename)
def write(filename,dataset,verbose = True):
    t = write_tecio(filename,dataset, verbose=verbose)
    t.close()
    
if __name__=='__main__':
    test = read_tecio('0605_ddes_profile_yxs_terminal_sample.szplt')
    test[0]['new'] = test[0][0]
    print(test[0].keys())
    t    = write_tecio('0605_ddes_profile_yxs_terminal_sample2.szplt',test,verbose = True)
    t.close()
